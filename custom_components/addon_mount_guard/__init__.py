"""Add-on Mount Guard — remédiation des stockages réseau tombés sous les add-ons."""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MIN_FREE_RATIO,
    CONF_MODE,
    CONF_MOUNT,
    CONF_MOUNTS,
    CONF_NOTIFY,
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SLUG,
    DEFAULT_MIN_FREE_RATIO,
    DEFAULT_NOTIFY,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_REPAIR,
    SERVICE_SET_MODE,
    SUBENTRY_TYPE_ADDON,
)
from .coordinator import (
    STORAGE_KEY,
    STORAGE_VERSION,
    MountGuardDataSource,
    MountGuardRuntimeData,
    guard_entries,
)
from .models import MODES
from .repair import RepairRunner
from .supervisor_api import SupervisorApiError, from_hass
from .websocket_api import async_register_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]

type MountGuardConfigEntry = ConfigEntry[MountGuardRuntimeData]

CARD_VERSION = "1.0.0"
CARD_URL = f"/{DOMAIN}/mount-guard-card.js"
# Même URL exacte pour les deux mécanismes d'injection : un module ES n'est
# évalué qu'une fois par URL, donc le double enregistrement est gratuit.
CARD_RESOURCE_URL = f"{CARD_URL}?v={CARD_VERSION}"

# Sans ce schéma, Home Assistant n'a aucun moyen de savoir que le domaine
# n'accepte pas de configuration YAML : un « addon_mount_guard: » égaré dans
# configuration.yaml serait accepté en silence au lieu d'être signalé.
# hassfest le réclame dès lors qu'async_setup est défini.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

EVENT_SUPERVISOR = "supervisor_event"

REPAIR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MOUNT): cv.string,
        vol.Optional("addon"): cv.string,
    }
)
SET_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MOUNT): cv.string,
        vol.Required(CONF_MODE): vol.In(MODES),
    }
)


# --- accès aux entrées ---------------------------------------------------

# `guard_entries` vit dans `coordinator.py`, avec `MountGuardRuntimeData` qu'il
# renvoie. Il est réexporté ici parce que c'est le nom sous lequel on le
# cherche, et parce que le laisser dans ce module créerait un cycle : le
# WebSocket en a besoin, et ce module importe le WebSocket.
__all__ = ["guard_entries"]


def _only_source(hass: HomeAssistant) -> MountGuardDataSource:
    entries = guard_entries(hass)
    if not entries:
        raise ServiceValidationError(
            "Add-on Mount Guard n'est pas configuré : rien à faire"
        )
    return entries[0][1].source


def resolve_mounts(source: MountGuardDataSource, data: dict[str, Any]) -> list[str]:
    """Traduit la cible d'un service en liste de montages.

    Un service ciblant un add-on agit sur **tous** ses montages : c'est ce que
    l'utilisateur veut dire par « répare Frigate », et le découper en autant
    d'appels lui ferait manquer celui qu'il ne connaît pas.

    Sans cible, tous les montages surveillés — un `repair` sans argument est le
    geste de quelqu'un qui veut que ça reparte, pas qui veut choisir.
    """
    mount = data.get(CONF_MOUNT)
    addon = data.get("addon")
    if mount:
        if mount not in source.table.mounts:
            raise ServiceValidationError(f"Montage inconnu : {mount}")
        return [mount]
    if addon:
        mounts = list(source.table.mounts_for(addon))
        if not mounts:
            raise ServiceValidationError(f"Add-on non surveillé : {addon}")
        return mounts
    return list(source.table.mounts)


# --- logique des services, au niveau module pour être testable -----------


async def async_repair(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Service `repair`.

    Au niveau module et non dans une closure de `async_setup_entry` : ce qui
    entre dans une closure devient invisible aux tests sans que rien ne le
    signale.
    """
    source = _only_source(hass)
    failures: list[str] = []
    for mount in resolve_mounts(source, data):
        try:
            await source.async_repair_now(mount)
        except Exception as err:
            # Volontairement large : un montage en échec ne doit pas empêcher
            # les autres d'être réparés.
            _LOGGER.warning("Réparation de %s en échec : %s", mount, err)
            failures.append(f"{mount} : {err}")
    if failures:
        raise HomeAssistantError("Réparation en échec — " + " ; ".join(failures))


@callback
def async_cancel(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Service `cancel`. Prend effet entre deux étapes, jamais au milieu
    d'une copie — voir `fileops.restore`."""
    source = _only_source(hass)
    for mount in resolve_mounts(source, data):
        source.request_cancel(mount)


async def async_set_mode(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Service `set_mode`.

    Le mode est une propriété **du montage**, stockée dans les options de
    l'entrée et non dans la sous-entrée d'un add-on : un montage est un objet
    physique unique, il ne peut pas être réparé de deux façons parce que deux
    add-ons l'ont déclaré différemment. Le conflit n'est pas arbitré ici, il est
    rendu impossible par la forme du stockage.
    """
    entries = guard_entries(hass)
    if not entries:
        raise ServiceValidationError("Add-on Mount Guard n'est pas configuré")
    entry = hass.config_entries.async_get_entry(entries[0][0])
    mount = data[CONF_MOUNT]
    mounts = dict(entry.options.get(CONF_MOUNTS, {}))
    if mount not in mounts:
        raise ServiceValidationError(f"Montage inconnu : {mount}")
    mounts[mount] = {**mounts[mount], CONF_MODE: data[CONF_MODE]}
    update_entry_and_ensure_reload(
        hass, entry, options={**entry.options, CONF_MOUNTS: mounts}
    )


# --- la carte ------------------------------------------------------------


def _get_lovelace_resources(hass: HomeAssistant):
    """Collection de ressources Lovelace, ou None si indisponible.

    On sonde défensivement plutôt que d'importer le composant lovelace : un
    import créerait une dépendance que hassfest exigerait de déclarer.

    Pas de repli sur `lovelace.get("resources")` : `hass.data["lovelace"]` était
    un dict jusqu'en 2025.1, c'est la dataclass `LovelaceData` depuis 2025.2, et
    le plancher de ce dépôt est 2026.1.
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        return None
    # Mode YAML : collection en lecture seule, c'est à l'utilisateur de
    # déclarer la ressource.
    if getattr(resources, "store", None) is None:
        return None
    return resources


async def async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Déclare la carte comme ressource Lovelace. True si c'est en place.

    **C'est le mécanisme à privilégier, et ce n'est pas qu'une question
    d'ordre.** Home Assistant charge `@webcomponents/scoped-custom-element-
    registry`, qui REMPLACE `window.customElements` par sa propre
    implémentation et sa propre table, sans jamais consulter le registre natif.
    Un module injecté par `add_extra_js_url` est évalué avant ce remplacement :
    sa définition atterrit dans le registre natif et reste invisible à Home
    Assistant, qui affiche « Custom element doesn't exist » définitivement.

    Les ressources Lovelace sont chargées par le panneau
    (`ha-panel-lovelace`), donc toujours après l'installation du polyfill. C'est
    exactement pourquoi les cartes distribuées en ressource — auto-entities,
    card-mod, mushroom — ne rencontrent jamais ce problème.

    Contre-intuitif : c'est le chargement le **plus rapide** qui échoue, le
    polyfill s'installant vers 110-130 ms.
    """
    try:
        resources = _get_lovelace_resources(hass)
        if resources is None:
            return False

        if not resources.loaded:
            await resources.async_get_info()

        for item in resources.async_items():
            url = item.get("url", "")
            if url.split("?")[0] != CARD_URL:
                continue
            if url == CARD_RESOURCE_URL:
                return True
            # Version changée : on met à jour plutôt que d'accumuler les
            # doublons, sinon deux versions du module coexisteraient et la
            # première enregistrée gagnerait.
            await resources.async_update_item(item["id"], {"url": CARD_RESOURCE_URL})
            _LOGGER.info("Ressource Lovelace mise à jour : %s", CARD_RESOURCE_URL)
            return True

        await resources.async_create_item({"res_type": "module", "url": CARD_RESOURCE_URL})
        _LOGGER.info("Ressource Lovelace enregistrée : %s", CARD_RESOURCE_URL)
        return True
    except Exception:
        # Volontairement large : l'enregistrement de la ressource ne doit jamais
        # empêcher le setup. À défaut, la carte reste injectée par
        # add_extra_js_url.
        _LOGGER.exception("Enregistrement de la ressource Lovelace impossible")
        return False


async def _async_setup_card(hass: HomeAssistant) -> None:
    """Rend la carte disponible, par le chemin le plus sûr d'abord."""
    if await async_register_lovelace_resource(hass):
        return

    _LOGGER.warning(
        "Ressources Lovelace non modifiables (mode YAML ?) : repli sur "
        "add_extra_js_url. Pour un chargement plus fiable, déclarez la "
        "ressource vous-même : url %s, type « module ».",
        CARD_RESOURCE_URL,
    )
    add_extra_js_url(hass, CARD_RESOURCE_URL)


# --- cycle de vie --------------------------------------------------------


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Setup global, une seule fois au démarrage de Home Assistant."""
    if DOMAIN + "_static_registered" in hass.data:
        return True

    card_path = Path(__file__).parent / "www" / "mount-guard-card.js"
    if not card_path.is_file():
        # Sans ce garde-fou on déclarerait une ressource vers une URL en 404 :
        # la carte ne serait jamais définie et Home Assistant afficherait une
        # carte en erreur sans que rien n'apparaisse dans les journaux.
        _LOGGER.error(
            "Fichier de la carte introuvable (%s) — la carte Lovelace ne sera pas "
            "disponible. Réinstallez l'intégration via HACS puis redémarrez.",
            card_path,
        )
        hass.data[DOMAIN + "_static_registered"] = True
        return True

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), False)]
    )
    # Après le démarrage : le composant lovelace n'est pas encore configuré au
    # moment où async_setup tourne.
    async_at_started(hass, _async_setup_card)
    hass.data[DOMAIN + "_static_registered"] = True
    return True


def addon_subentries(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Les sous-entrées d'add-on, sous la forme attendue par `build_mount_table`."""
    return [
        {CONF_SLUG: subentry.data.get(CONF_SLUG), CONF_MOUNTS: subentry.data.get(CONF_MOUNTS, [])}
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_ADDON
    ]


def option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Option d'abord, donnée ensuite, défaut en dernier.

    L'inverse ferait réafficher la valeur du formulaire initial à chaque
    ouverture des options, et l'utilisateur écraserait son propre réglage en
    validant sans rien toucher.
    """
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, entry: MountGuardConfigEntry) -> bool:
    """Met en place l'entrée unique."""
    try:
        api = from_hass(hass)
    except SupervisorApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    source_holder: dict[str, MountGuardDataSource] = {}

    runner = RepairRunner(
        api=api,
        run_executor=hass.async_add_executor_job,
        # Indirection volontaire : le runner publie via la source, qui n'existe
        # pas encore — elle a besoin du runner pour être construite. Une
        # référence différée plutôt qu'un attribut posé après coup, qui serait
        # silencieusement `None` si on oubliait de le poser.
        publish=lambda remediation: source_holder["source"].publish(remediation),
        now=dt_util.utcnow,
        retry_interval=option(entry, CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
    )

    source = MountGuardDataSource(
        hass,
        api,
        runner,
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        retry_interval=option(entry, CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL),
        min_free_ratio=option(entry, CONF_MIN_FREE_RATIO, DEFAULT_MIN_FREE_RATIO),
        notify=option(entry, CONF_NOTIFY, DEFAULT_NOTIFY),
    )
    source_holder["source"] = source

    # Posé en première instruction utile : `guard_entries` s'en sert pour
    # décider si les services ont quelque chose à faire.
    entry.runtime_data = MountGuardRuntimeData(api=api, source=source, runner=runner)

    await source.async_load()
    source.rebuild_table(entry.options.get(CONF_MOUNTS, {}), addon_subentries(entry))

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=source.async_update,
        update_interval=timedelta(
            seconds=option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )
    source.coordinator = coordinator
    entry.runtime_data.coordinator = coordinator

    await coordinator.async_config_entry_first_refresh()

    # Le Supervisor annonce ses problèmes bien avant que le polling ne les voie.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_SUPERVISOR, source.async_handle_supervisor_event)
    )

    _async_register_services(hass)
    # Après `runtime_data` : la commande lit `guard_entries`, qui l'exige.
    async_register_websocket(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Enregistre les trois services, une seule fois.

    Les points d'entrée sont minces à dessein : la logique vit au niveau module,
    où les tests l'atteignent.
    """
    if hass.services.has_service(DOMAIN, SERVICE_REPAIR):
        return

    async def handle_repair(call: ServiceCall) -> None:
        await async_repair(hass, dict(call.data))

    async def handle_cancel(call: ServiceCall) -> None:
        async_cancel(hass, dict(call.data))

    async def handle_set_mode(call: ServiceCall) -> None:
        await async_set_mode(hass, dict(call.data))

    hass.services.async_register(DOMAIN, SERVICE_REPAIR, handle_repair, schema=REPAIR_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL, handle_cancel, schema=REPAIR_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_MODE, handle_set_mode, schema=SET_MODE_SCHEMA
    )


@callback
def update_entry_and_ensure_reload(
    hass: HomeAssistant, entry: ConfigEntry, **updates: Any
) -> None:
    """Met à jour l'entrée en garantissant qu'elle sera rechargée.

    Pas `async_update_reload_and_abort` : il programme lui-même un rechargement
    alors qu'un listener de mise à jour est enregistré, ce que Home Assistant
    déprécie avec une casse annoncée en 2026.12.

    Deux cas n'appellent aucun listener et exigent donc un rechargement
    explicite : l'entrée n'a pas changé — reconfiguration resoumise à
    l'identique, `async_update_entry` renvoyant `False` sans rien notifier — et
    aucun listener n'est enregistré, entrée désactivée ou setup interrompu avant
    `add_update_listener`.

    Le helper vit ici et non dans `config_flow.py`, qui n'est pas importable
    sous les mocks : un helper qui y resterait ne serait couvert que par analyse
    de source.
    """
    changed = hass.config_entries.async_update_entry(entry, **updates)
    if not changed or not entry.update_listeners:
        hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée après toute modification.

    Ce listener est le SEUL endroit qui recharge, et c'est ce que Home Assistant
    attend d'une intégration qui en enregistre un. Il couvre aussi l'ajout, la
    modification et la suppression d'une sous-entrée : la table inversée est
    reconstruite par `async_setup_entry`, donc un rechargement suffit et il n'y
    a pas deux chemins de reconstruction à garder d'accord.

    **Ne pas le conditionner aux options** pour éviter un double rechargement :
    ça rendrait une reconfiguration sans effet, puisqu'elle ne touche que les
    données. **Ne pas passer à `OptionsFlowWithReload`** non plus, malgré son
    nom engageant : sa propre docstring interdit de l'employer quand
    l'intégration enregistre un listener de mise à jour.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MountGuardConfigEntry) -> bool:
    """Décharge l'entrée.

    Rien à nettoyer d'autre : les écouteurs sont posés par `async_on_unload`, et
    Home Assistant supprime `runtime_data` lui-même quand le déchargement
    réussit.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: MountGuardConfigEntry) -> None:
    """Retire les services quand la dernière entrée est supprimée.

    Au retrait et non au déchargement : un rechargement passe par unload puis
    setup, et retirer les services entre les deux laisserait une fenêtre —
    le temps du setup des plateformes, entrées/sorties disque comprises —
    pendant laquelle une automatisation reçoit `ServiceNotFound`. Les
    rechargements sont fréquents : options, sous-entrées, reconfiguration.
    """
    # Pas d'exclusion de l'entrée en cours de suppression : Home Assistant la
    # décharge avant d'appeler ce handler, donc le filtre d'état l'écarte déjà.
    # Se fier à sa présence dans la collection serait fragile : HA a inversé
    # l'ordre en 2025.3.
    if guard_entries(hass):
        return
    for service in (SERVICE_REPAIR, SERVICE_CANCEL, SERVICE_SET_MODE):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
