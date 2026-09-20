"""Le cycle de surveillance, et l'état de tous les montages.

Ce module **n'hérite de rien**. `DataUpdateCoordinator` est instancié par
`__init__.py` — un appel, pas un héritage — et reçoit `async_update` d'ici. La
raison est écrite dans `tests/conftest.py` et mérite d'être répétée : sous les
mocks, une classe dérivée d'une base MagicMock *est* un MagicMock. Elle
s'importe, s'instancie, et toutes ses méthodes sont muettes. Pas d'erreur, CI
verte, code jamais exécuté. Tout ce qui décide d'arrêter un add-on doit donc
vivre dans une classe ordinaire.

**L'état persistant est partagé entre deux mémoires, et les deux sont
nécessaires.** Le `Store` retient l'intention — quel montage était dégradé,
quels add-ons nous avions arrêtés, ce que dit le journal. Le système de fichiers
retient les fichiers, par la seule présence de `<chemin>_local`. Un fichier
d'état peut mentir sur ce que contient le disque ; le disque ne dit pas qui
relancer. Chaque cycle réconcilie les deux, ce qui fait de la reprise après
redémarrage un cas ordinaire plutôt qu'un chemin à part.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import fileops, machine
from .const import (
    DEFAULT_MIN_FREE_RATIO,
    DEFAULT_RETRY_INTERVAL,
    DOMAIN,
    EVENT_MOUNT_GUARD,
    FAILURES_BEFORE_ISSUE,
)
from .models import (
    Remediation,
    RemediationAddon,
    from_wire,
    needs_remediation,
    new_remediation,
    to_wire,
)
from .mount_table import MountConfig, MountTable, build_mount_table
from .reachability import async_is_reachable, probe_port
from .repair import RepairContext, RepairRunner
from .supervisor_api import SupervisorApi, SupervisorApiError

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.state"

#: Retard d'écriture du `Store`. Une remédiation publie une douzaine de fois en
#: deux minutes ; écrire à chaque fois userait la carte SD pour un état qu'on
#: relit une seule fois, au démarrage.
SAVE_DELAY = 10


@dataclass
class MountGuardRuntimeData:
    """Ce que l'intégration garde en mémoire pour son entrée unique.

    Porté par `entry.runtime_data` et non par `hass.data[DOMAIN][entry_id]` :
    Home Assistant le supprime lui-même au déchargement réussi, alors qu'un
    dictionnaire global devrait être vidé à la main et qu'une entrée jamais
    chargée y laisserait ses tâches jusqu'au redémarrage.

    `coordinator` est posé par `__init__.py` après construction : le
    `DataUpdateCoordinator` a besoin de `source.async_update` pour être
    construit, donc la source existe forcément avant lui.
    """

    api: SupervisorApi
    source: MountGuardDataSource
    runner: RepairRunner
    coordinator: Any = None


def guard_entries(hass: HomeAssistant) -> list[tuple[str, MountGuardRuntimeData]]:
    """Entrées utilisables, dans l'ordre d'ajout à la collection.

    Deux filtres, et les deux sont nécessaires :

    - `runtime_data` n'existe pas tant qu'`async_setup_entry` ne l'a pas posé,
      et Home Assistant le supprime **au déchargement réussi seulement**. Ça
      écarte les entrées désactivées, ignorées et déchargées sans rien
      entretenir à la main.
    - l'état, parce que `runtime_data` est posé en première instruction et
      **survit à un setup qui échoue ensuite**. Sans ce filtre, une entrée
      restée en erreur compte encore comme utilisable et retient les services
      indéfiniment.

    Une liste alors que `single_config_entry` est vrai : la contrainte porte sur
    ce que l'utilisateur peut ajouter, pas sur ce qui peut exister le temps d'un
    rechargement.
    """
    return [
        (entry.entry_id, data)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and (data := getattr(entry, "runtime_data", None)) is not None
    ]


def build_unique_id(entry_id: str, *parts: str) -> str:
    """Identifiant unique d'une entité.

    Dérivé de l'`entry_id` (ou du `subentry_id`) et du **nom du montage**,
    jamais d'une option modifiable. Un identifiant qui dépend d'un réglage
    signifie qu'en changer crée des entités neuves et orpheline les anciennes :
    tableau de bord cassé, historique perdu, automatisations muettes. Le nom du
    montage, lui, ne se change pas — le renommer dans Home Assistant crée un
    autre montage.
    """
    return "_".join((entry_id, *parts))


class MountGuardDataSource:
    """Surveille les montages, décide, et délègue la réparation.

    Volontairement une classe ordinaire : voir l'en-tête du module.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: SupervisorApi,
        runner: RepairRunner,
        store: Store,
        *,
        retry_interval: int = DEFAULT_RETRY_INTERVAL,
        min_free_ratio: float = DEFAULT_MIN_FREE_RATIO,
        notify: bool = True,
    ) -> None:
        self.hass = hass
        self.api = api
        self.runner = runner
        self.store = store
        self.retry_interval = retry_interval
        self.min_free_ratio = min_free_ratio
        self.notify = notify

        self.coordinator: Any = None
        self._table = MountTable(mounts={}, by_addon={})
        self._states: dict[str, Remediation] = {}
        self._we_stopped: dict[str, bool] = {}
        self._subscribers: set[Callable[[dict[str, Any]], None]] = set()
        self._in_update = False

    # --- configuration ---------------------------------------------------

    def rebuild_table(
        self,
        mount_options: Mapping[str, Mapping[str, Any]],
        subentries: Iterable[Mapping[str, Any]],
    ) -> None:
        """Reconstruit les deux tables et fait le ménage.

        Appelée au chargement et à chaque ajout, modification ou suppression de
        sous-entrée. Les états des montages qui ne sont plus surveillés sont
        oubliés : les garder ferait afficher indéfiniment sur la carte un
        montage que l'utilisateur vient justement de retirer.
        """
        self._table = build_mount_table(mount_options, subentries)
        for name in list(self._states):
            if name not in self._table.mounts:
                self._states.pop(name, None)
        for name, config in self._table.mounts.items():
            current = self._states.get(name)
            if current is None:
                self._states[name] = new_remediation(name, config.path, config.mode)
            elif current.mode != config.mode or current.path != config.path:
                self._states[name] = replace(current, mode=config.mode, path=config.path)

    @property
    def table(self) -> MountTable:
        return self._table

    def context(self) -> RepairContext:
        return RepairContext(
            table=self._table,
            # Une fonction, pas un instantané : une séquence dure plusieurs
            # minutes, et la garde de relance doit interroger la situation au
            # moment où elle relance.
            states=lambda: dict(self._states),
            we_stopped=self._we_stopped,
        )

    # --- persistance -----------------------------------------------------

    async def async_load(self) -> None:
        """Relit l'état d'avant l'arrêt.

        Un montage persisté en `repairing` est ramené à `pending` : la séquence
        qui le tenait n'existe plus, et `repairing` empêcherait `observe` de le
        regarder — il resterait figé pour toujours. `pending` le remet dans le
        flux ordinaire, où la présence de `<chemin>_local` décidera de la suite.
        """
        stored = await self.store.async_load()
        if not isinstance(stored, dict):
            return
        self._we_stopped = {
            slug: bool(value)
            for slug, value in (stored.get("we_stopped") or {}).items()
            if isinstance(slug, str)
        }
        for raw in (stored.get("mounts") or {}).values():
            remediation = from_wire(raw)
            if remediation is None:
                _LOGGER.warning("État persisté illisible, ignoré : %s", raw)
                continue
            if remediation.state == "repairing":
                remediation = replace(remediation, state="pending", step=None)
            self._states[remediation.mount] = remediation

    def _schedule_save(self) -> None:
        self.store.async_delay_save(self._snapshot, SAVE_DELAY)

    def _snapshot(self) -> dict[str, Any]:
        return {
            "mounts": {name: to_wire(rem) for name, rem in self._states.items()},
            "we_stopped": dict(self._we_stopped),
        }

    # --- publication -----------------------------------------------------

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Abonne le WebSocket. Rend la fonction de désabonnement.

        Le WebSocket existe pour une seule raison : pousser la progression du
        rapatriement sans attendre le cycle de polling. L'attribut d'entité
        arrive de toute façon, mais une minute plus tard — une barre qui bouge
        une fois par minute ne dit rien de plus qu'un texte figé.
        """
        self._subscribers.add(callback)
        return lambda: self._subscribers.discard(callback)

    def snapshot(self) -> list[Remediation]:
        """L'état de tous les montages, pour un abonné qui arrive en cours de
        route. Sans lui, une carte ouverte pendant une période calme
        n'afficherait rien jusqu'au premier changement."""
        return list(self._states.values())

    def publish(self, remediation: Remediation) -> None:
        """Point d'entrée unique de toute mise à jour d'état.

        Passé au `RepairRunner` à la construction, et appelé aussi par le cycle
        de polling. Un seul chemin : les trois canaux — attribut d'entité,
        WebSocket, événement — ne peuvent pas diverger, et un champ ajouté au
        contrat arrive partout sans rien toucher ici.
        """
        previous = self._states.get(remediation.mount)
        self._states[remediation.mount] = remediation

        if previous is None or previous.state != remediation.state:
            self._fire_event(remediation, previous)

        payload = to_wire(remediation)
        for callback in list(self._subscribers):
            try:
                callback(payload)
            except Exception:
                # Un abonné en échec — connexion WebSocket fermée entre-temps —
                # ne doit pas interrompre la remédiation en cours.
                _LOGGER.exception("Abonné en échec, ignoré")

        self._schedule_save()
        # Pendant `async_update`, le coordinator reçoit déjà le dictionnaire en
        # valeur de retour : le lui pousser ici en plus le ferait notifier ses
        # entités au milieu de son propre cycle.
        if self.coordinator is not None and not self._in_update:
            self.coordinator.async_set_updated_data(dict(self._states))

    def _fire_event(self, remediation: Remediation, previous: Remediation | None) -> None:
        self.hass.bus.async_fire(
            EVENT_MOUNT_GUARD,
            {
                "mount": remediation.mount,
                "from": previous.state if previous else None,
                "to": remediation.state,
                "step": remediation.step,
                "error": remediation.last_error,
                "addons": [addon.slug for addon in remediation.addons],
            },
        )

    # --- le cycle --------------------------------------------------------

    async def async_update(self) -> dict[str, Remediation]:
        """Un relevé de tous les montages surveillés.

        Ne lève que si le Supervisor est injoignable : une panne d'un montage
        est une information, pas un échec de cycle. Laisser remonter l'exception
        d'un seul montage ferait passer tous les autres en « indisponible ».
        """
        try:
            mounts = {mount.name: mount for mount in await self.api.mounts()}
            addons = {addon.slug: addon for addon in await self.api.addons()}
        except SupervisorApiError as err:
            raise UpdateFailed(f"Superviseur injoignable : {err}") from err

        self._in_update = True
        try:
            for name, config in self._table.mounts.items():
                await self._observe_mount(name, config, mounts.get(name), addons)
        finally:
            self._in_update = False
        return dict(self._states)

    async def _observe_mount(
        self, name: str, config: MountConfig, mount: Any, addons: Mapping[str, Any]
    ) -> None:
        if self.runner.is_running(name):
            # La séquence pilote, et elle publie elle-même. Un relevé arrivé au
            # milieu de l'étape 3 verrait un montage absent qu'elle vient de
            # recharger.
            return

        current = self._states.get(name) or new_remediation(name, config.path, config.mode)
        path = Path(config.path)
        now = dt_util.utcnow()

        mounted = bool(await self.hass.async_add_executor_job(fileops.is_mounted, path))
        stashed = bool(
            await self.hass.async_add_executor_job(fileops.stash_dir(path).is_dir)
        )
        reachable = False
        if not mounted or stashed:
            # Sondé seulement quand ça sert. Ouvrir une connexion TCP vers le
            # NAS toutes les soixante secondes pour un montage en bon état est
            # gratuit pour nous et pas pour lui.
            reachable = await async_is_reachable(
                config.host, port=probe_port(getattr(mount, "type", None))
            )

        updated = machine.observe(
            current, mounted=mounted, reachable=reachable, now=now, stashed=stashed
        )
        updated = self._with_addon_states(updated, addons)

        if updated != current:
            self.publish(updated)
            self._check_issue(updated)

        await self._react(config, updated, path)

    def _with_addon_states(
        self, remediation: Remediation, addons: Mapping[str, Any]
    ) -> Remediation:
        """Rafraîchit l'état des add-ons du montage.

        `held` est **dérivé ici** et pas seulement posé par l'étape 5 : sans
        ça, un add-on maintenu arrêté repasserait à « arrêté » au premier cycle
        de polling, et la carte cesserait d'expliquer pourquoi il ne tourne pas.
        """
        states = dict(self._states)
        entries = []
        for slug in self._table.slugs_for(remediation.mount):
            info = addons.get(slug)
            if info is None:
                entries.append(("unknown", slug, slug))
                continue
            if info.running:
                state = "started"
            elif any(
                needs_remediation(states[other])
                for other in self._table.other_mounts_of(slug, remediation.mount)
                if other in states
            ):
                state = "held"
            else:
                state = "stopped"
            entries.append((state, slug, info.name))

        return replace(
            remediation,
            addons=tuple(
                RemediationAddon(slug=slug, name=name, state=state)  # type: ignore[arg-type]
                for state, slug, name in entries
            ),
        )

    async def _react(self, config: MountConfig, remediation: Remediation, path: Path) -> None:
        """Ce qu'on fait de l'état qu'on vient de constater."""
        if remediation.state == "pending":
            # Lancée hors du cycle : une séquence dure des minutes, et l'y
            # attendre bloquerait la surveillance de tous les autres montages.
            self.hass.async_create_task(self._async_repair(config, remediation))
            return

        if remediation.state != "degraded":
            return

        if config.mode == "stop_only":
            # Étape 1 dès la panne, sans attendre le retour du NAS : c'est tout
            # ce que ce mode promet.
            await self.runner.async_stop_addons(config, remediation, self.context())
            return

        free = await self.hass.async_add_executor_job(fileops.free_ratio, path)
        slugs = machine.disk_guard(
            remediation, free_ratio=free, threshold=self.min_free_ratio
        )
        if slugs:
            _LOGGER.warning(
                "Espace libre à %.0f %% sous %s : arrêt de %s",
                free * 100,
                path,
                ", ".join(slugs),
            )
            self._notify(
                f"mount_guard_disk_{config.mount}",
                "Espace disque local insuffisant",
                f"Le repli local de « {config.mount} » a rempli le disque "
                f"({free * 100:.0f} % libres). Les add-ons {', '.join(slugs)} ont été "
                "arrêtés pour protéger l'installation.",
            )
            await self.runner.async_stop_addons(config, remediation, self.context())

    async def _async_repair(self, config: MountConfig, remediation: Remediation) -> None:
        result = await self.runner.async_run(config, remediation, self.context())
        self.publish(result)
        self._check_issue(result)

    # --- réparation à la demande ------------------------------------------

    async def async_repair_now(self, mount: str) -> None:
        """Service `repair` : court-circuite le délai de réessai.

        C'est la contrepartie du choix fait dans `RepairRunner._fail`, où une
        annulation reprogramme quand même un réessai ordinaire. L'utilisateur
        qui veut relancer tout de suite a ce bouton ; celui qui ne fait rien
        n'est pas abandonné.
        """
        config = self._table.mounts.get(mount)
        if config is None:
            raise ValueError(f"Montage inconnu : {mount}")
        current = self._states.get(mount) or new_remediation(mount, config.path, config.mode)
        await self._async_repair(config, replace(current, next_retry_at=None))

    def request_cancel(self, mount: str) -> None:
        self.runner.request_cancel(mount)

    # --- événements du Supervisor ------------------------------------------

    async def async_handle_supervisor_event(self, event: Any) -> None:
        """Réagit à `supervisor_event` sans attendre le prochain relevé.

        Le Supervisor annonce ses problèmes (`issue_changed`, `issue_removed`)
        bien avant que notre polling ne les voie. On ne fait pas confiance au
        contenu pour décider quoi que ce soit — on se contente de déclencher un
        relevé, qui ira lire `/proc/mounts`, la seule source qui dise ce que voit
        le conteneur core.
        """
        data = getattr(event, "data", None) or {}
        if data.get("event") not in ("issue_changed", "issue_removed"):
            return
        issue = data.get("data") or {}
        if issue.get("type") != "mount_failed":
            return
        reference = issue.get("reference")
        if reference and reference not in self._table.mounts:
            return
        _LOGGER.info("Le Superviseur signale un problème de montage (%s)", reference)
        if self.coordinator is not None:
            await self.coordinator.async_request_refresh()

    # --- réparations Home Assistant et notifications -----------------------

    def _check_issue(self, remediation: Remediation) -> None:
        """Ouvre une réparation après trois échecs d'affilée.

        Trois, parce que moins ferait remonter une panne transitoire du NAS et
        plus ferait attendre une heure avant que l'utilisateur apprenne que
        l'automatique ne s'en sort pas. Le compte est dérivé du journal, jamais
        tenu à part — voir `machine.consecutive_failures`.
        """
        issue_id = f"repair_failed_{remediation.mount}"
        failures = machine.consecutive_failures(remediation)
        if failures >= FAILURES_BEFORE_ISSUE:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="repair_failed",
                translation_placeholders={
                    "mount": remediation.mount,
                    "error": remediation.last_error or "",
                },
            )
        elif failures == 0:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _notify(self, notification_id: str, title: str, message: str) -> None:
        if not self.notify:
            return
        persistent_notification.async_create(
            self.hass, message, title=title, notification_id=notification_id
        )
