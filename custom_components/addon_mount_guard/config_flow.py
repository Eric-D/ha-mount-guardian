"""Flux de configuration.

Une seule entrée (`single_config_entry`), et **une sous-entrée par add-on
surveillé**. La forme du stockage porte à elle seule la décision la plus
structurante du projet :

- les options de l'entrée contiennent `mounts[<nom>] = {host, mode, usage,
  overwrite}` — la configuration **du montage** ;
- la sous-entrée d'un add-on ne contient que `{slug, mounts: [<noms>]}`.

Un montage est un objet physique unique : il ne peut pas être réparé de deux
façons parce que deux add-ons l'ont déclaré différemment, ni pointer vers deux
NAS. En le rangeant au niveau de l'entrée, le conflit n'est pas arbitré — il est
rendu impossible. Le formulaire d'ajout d'un add-on demande quand même hôte et
mode, mais les pré-remplit et les verrouille quand le montage est déjà connu.

Ce module n'est **pas importable** sous les mocks de `tests/conftest.py` :
`ConfigFlow` y est un MagicMock, et une classe dérivée d'une base mockée est
elle-même un MagicMock — elle s'importe, s'instancie, et toutes ses méthodes
sont muettes. Ne pas y mettre de logique : elle ne serait couverte par rien.
C'est pourquoi `update_entry_and_ensure_reload` vit dans `__init__.py`.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import update_entry_and_ensure_reload
from .const import (
    CONF_CONCURRENCY,
    CONF_HOST,
    CONF_MIN_FREE_RATIO,
    CONF_MODE,
    CONF_MOUNTS,
    CONF_NOTIFY,
    CONF_OVERWRITE,
    CONF_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SLUG,
    DEFAULT_CONCURRENCY,
    DEFAULT_MIN_FREE_RATIO,
    DEFAULT_NOTIFY,
    DEFAULT_OVERWRITE,
    DEFAULT_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_CONCURRENCY,
    MAX_MIN_FREE_RATIO,
    MAX_RETRY_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_CONCURRENCY,
    MIN_RETRY_INTERVAL,
    MIN_SCAN_INTERVAL,
    OVERWRITE_MODES,
    SUBENTRY_TYPE_ADDON,
)
from .models import MODES
from .reachability import async_is_reachable, probe_port
from .supervisor_api import SupervisorApiError, from_hass

_LOGGER = logging.getLogger(__name__)


def _options_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=current[CONF_SCAN_INTERVAL]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL, step=5,
                    unit_of_measurement="s", mode="box",
                )
            ),
            vol.Optional(
                CONF_RETRY_INTERVAL, default=current[CONF_RETRY_INTERVAL]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_RETRY_INTERVAL, max=MAX_RETRY_INTERVAL, step=10,
                    unit_of_measurement="s", mode="box",
                )
            ),
            vol.Optional(
                CONF_MIN_FREE_RATIO, default=current[CONF_MIN_FREE_RATIO]
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=MAX_MIN_FREE_RATIO, step=0.01, mode="slider"
                )
            ),
            vol.Optional(CONF_NOTIFY, default=current[CONF_NOTIFY]): BooleanSelector(),
        }
    )


class MountGuardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flux de configuration d'Add-on Mount Guard."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Une seule étape : les réglages globaux.

        Aucun montage n'est demandé ici. Ils arrivent avec les add-ons, par des
        sous-entrées : c'est un add-on qu'on surveille, et déclarer un montage
        que rien n'utilise n'aurait aucun effet — `build_mount_table` l'écarte.
        """
        # Avant tout le reste : inutile de montrer un formulaire pour une
        # entrée qui sera refusée.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                from_hass(self.hass)
            except SupervisorApiError:
                # `dependencies: ["hassio"]` empêche normalement d'arriver ici :
                # Home Assistant ne met pas l'intégration en place sans le
                # composant. Ce message couvre le résidu, et vaut mieux qu'un
                # formulaire qui accepte puis une entrée qui ne démarre pas.
                errors["base"] = "no_supervisor"
            else:
                return self.async_create_entry(
                    title="Add-on Mount Guard",
                    data={},
                    options={**user_input, CONF_MOUNTS: {}},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_options_schema(
                {
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_RETRY_INTERVAL: DEFAULT_RETRY_INTERVAL,
                    CONF_MIN_FREE_RATIO: DEFAULT_MIN_FREE_RATIO,
                    CONF_NOTIFY: DEFAULT_NOTIFY,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """L'entrée reste dans la signature — c'est Home Assistant qui appelle —
        mais n'est plus transmise : le flux la retrouve par sa propriété."""
        return MountGuardOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Un type de sous-entrée : l'add-on surveillé."""
        return {SUBENTRY_TYPE_ADDON: AddonSubentryFlow}


class MountGuardOptionsFlow(OptionsFlow):
    """Options globales.

    Pas d'`__init__` : la classe de base expose l'entrée via sa propriété
    `config_entry` depuis 2024.12. La stocker soi-même est ce que faisait
    `OptionsFlowWithConfigEntry`, que Home Assistant met en erreur pour ses
    propres intégrations.

    Pas non plus d'`OptionsFlowWithReload`, malgré son nom engageant : sa
    docstring interdit de l'employer quand l'intégration enregistre un listener
    de mise à jour, ce qui est notre cas — et ce listener doit rester le seul
    point de rechargement.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # `mounts` est réinjecté tel quel : il n'est pas dans ce formulaire,
            # et le laisser tomber effacerait la configuration de tous les
            # montages au premier changement d'intervalle.
            return self.async_create_entry(
                title="",
                data={**user_input, CONF_MOUNTS: self.config_entry.options.get(CONF_MOUNTS, {})},
            )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                {
                    CONF_SCAN_INTERVAL: options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_RETRY_INTERVAL: options.get(
                        CONF_RETRY_INTERVAL, DEFAULT_RETRY_INTERVAL
                    ),
                    CONF_MIN_FREE_RATIO: options.get(
                        CONF_MIN_FREE_RATIO, DEFAULT_MIN_FREE_RATIO
                    ),
                    CONF_NOTIFY: options.get(CONF_NOTIFY, DEFAULT_NOTIFY),
                }
            ),
        )


class AddonSubentryFlow(ConfigSubentryFlow):
    """Ajout et modification d'un add-on surveillé.

    Deux étapes : choisir l'add-on, puis ses montages et leurs réglages. Les
    deux listes viennent du Supervisor — saisir un slug à la main est la
    meilleure façon de surveiller un add-on qui n'existe pas, sans que rien ne
    le dise avant la première panne.
    """

    def __init__(self) -> None:
        self._slug: str | None = None

    # --- ajout -----------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self.async_step_addon(user_input)

    async def async_step_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        try:
            api = from_hass(self.hass)
            addons = await api.addons()
        except SupervisorApiError:
            return self.async_abort(reason="no_supervisor")

        entry = self._get_entry()
        already = {
            sub.data.get(CONF_SLUG)
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_TYPE_ADDON
        }
        choices = [
            SelectOptionDict(value=addon.slug, label=addon.name)
            for addon in sorted(addons, key=lambda a: a.name.lower())
            if addon.slug not in already
        ]
        if not choices:
            return self.async_abort(reason="no_addons")

        if user_input is not None:
            self._slug = user_input[CONF_SLUG]
            return await self.async_step_mounts()

        return self.async_show_form(
            step_id="addon",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SLUG): SelectSelector(
                        SelectSelectorConfig(options=choices, mode=SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_mounts(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Les montages de cet add-on, et les réglages de chacun.

        Les montages dont l'usage est `backup` sont écartés de la liste :
        `/backup` n'a pas de `<nom>` dans son chemin, donc la mise de côté
        écrirait `/backup_local` à la racine du conteneur, et aucun add-on n'y
        écrit en continu. Les refuser ici vaut mieux que les accepter sans les
        avoir testés.
        """
        try:
            api = from_hass(self.hass)
            mounts = [mount for mount in await api.mounts() if mount.supported]
        except SupervisorApiError:
            return self.async_abort(reason="no_supervisor")

        if not mounts:
            return self.async_abort(reason="no_mounts")

        entry = self._get_entry()
        known = dict(entry.options.get(CONF_MOUNTS, {}))

        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input[CONF_MOUNTS]
            host = user_input[CONF_HOST].strip()
            by_name = {mount.name: mount for mount in mounts}
            if not await async_is_reachable(
                host, port=probe_port(by_name[selected[0]].type)
            ):
                # Un avertissement, pas un refus : le NAS peut être éteint au
                # moment où on configure, et c'est même le cas le plus probable
                # pour quelqu'un qui installe cette intégration après une
                # panne.
                _LOGGER.warning("%s ne répond pas — configuration acceptée quand même", host)

            for name in selected:
                # Les réglages du MONTAGE, écrits dans les options de l'entrée.
                # Une sous-entrée ajoutée plus tard les retrouvera au lieu d'en
                # proposer d'autres.
                known[name] = {
                    CONF_HOST: host,
                    CONF_MODE: user_input[CONF_MODE],
                    CONF_OVERWRITE: user_input[CONF_OVERWRITE],
                    CONF_CONCURRENCY: int(user_input[CONF_CONCURRENCY]),
                    "usage": by_name[name].usage,
                }
            update_entry_and_ensure_reload(
                self.hass, entry, options={**entry.options, CONF_MOUNTS: known}
            )
            return self.async_create_entry(
                title=self._slug or "add-on",
                data={CONF_SLUG: self._slug, CONF_MOUNTS: selected},
            )

        # Pré-remplissage à partir du premier montage déjà connu : hôte et mode
        # sont des propriétés du montage, pas de l'add-on, et en proposer
        # d'autres donnerait l'illusion qu'on peut les faire diverger.
        seed = next((known[name] for name in known), {})
        return self.async_show_form(
            step_id="mounts",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MOUNTS): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=mount.name, label=f"{mount.name} ({mount.usage})"
                                )
                                for mount in mounts
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Required(CONF_HOST, default=seed.get(CONF_HOST, "")): TextSelector(),
                    vol.Required(
                        CONF_MODE, default=seed.get(CONF_MODE, MODES[0])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(MODES),
                            translation_key="mode",
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Required(
                        CONF_OVERWRITE, default=seed.get(CONF_OVERWRITE, DEFAULT_OVERWRITE)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(OVERWRITE_MODES),
                            translation_key="overwrite",
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Required(
                        CONF_CONCURRENCY,
                        default=seed.get(CONF_CONCURRENCY, DEFAULT_CONCURRENCY),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_CONCURRENCY, max=MAX_CONCURRENCY, step=1, mode="slider"
                        )
                    ),
                }
            ),
            errors=errors,
        )

    # --- modification ------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Modifie les montages d'un add-on déjà surveillé."""
        self._slug = self._get_reconfigure_subentry().data.get(CONF_SLUG)
        return await self.async_step_mounts(user_input)
