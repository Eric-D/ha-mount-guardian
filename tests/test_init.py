"""Le câblage : services, ressource Lovelace, rechargement.

Une partie de ce fichier lit la **source** plutôt que d'exécuter le code. Ce
n'est pas de la paresse : `async_setup_entry` ne s'exécute pas sous les mocks —
il construit un `DataUpdateCoordinator` qui n'existe pas — mais ce qu'il oublie
de faire est silencieux. Une affectation de `runtime_data` absente rend
l'intégration entièrement muette, CI verte.
"""
from __future__ import annotations

import pathlib
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import custom_components.addon_mount_guard as mg
from custom_components.addon_mount_guard.coordinator import (
    ConfigEntryState,
    MountGuardDataSource,
)
from custom_components.addon_mount_guard.mount_table import build_mount_table

SOURCE = (
    pathlib.Path(mg.__file__).parent / "__init__.py"
).read_text("utf-8")

OPTIONS = {
    "nas_media": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "media"},
    "nas_config": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "share"},
}
SUBENTRIES = [{"slug": "frigate", "mounts": ["nas_media", "nas_config"]},
              {"slug": "motioneye", "mounts": ["nas_media"]}]


def make_source():
    source = MountGuardDataSource(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    source.rebuild_table(OPTIONS, SUBENTRIES)
    return source


def make_hass(entries):
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = entries
    return hass


def make_entry(source, *, loaded=True):
    entry = SimpleNamespace(
        entry_id="entry1",
        state=ConfigEntryState.LOADED if loaded else "other",
        runtime_data=SimpleNamespace(source=source),
        options={},
        data={},
        update_listeners=[object()],
        subentries={},
    )
    return entry


# --- sélection des entrées ------------------------------------------------


class TestGuardEntries:
    def test_a_loaded_entry_with_runtime_data_counts(self):
        source = make_source()
        hass = make_hass([make_entry(source)])
        assert [eid for eid, _ in mg.guard_entries(hass)] == ["entry1"]

    def test_an_entry_without_runtime_data_is_skipped(self):
        """`runtime_data` n'existe pas tant qu'`async_setup_entry` ne l'a pas
        posé, et Home Assistant le supprime au déchargement réussi. Ça écarte
        les entrées désactivées, ignorées et déchargées sans rien entretenir."""
        entry = make_entry(make_source())
        del entry.runtime_data
        assert mg.guard_entries(make_hass([entry])) == []

    def test_an_entry_in_error_is_skipped(self):
        """`runtime_data` est posé en première instruction et survit à un setup
        qui échoue ensuite. Sans le filtre d'état, une entrée restée en erreur
        retiendrait les services indéfiniment."""
        assert mg.guard_entries(make_hass([make_entry(make_source(), loaded=False)])) == []


# --- résolution des cibles ------------------------------------------------


class TestResolveMounts:
    def test_a_mount_target_is_itself(self):
        assert mg.resolve_mounts(make_source(), {"mount": "nas_media"}) == ["nas_media"]

    def test_an_addon_target_covers_all_its_mounts(self):
        """C'est ce que l'utilisateur veut dire par « répare Frigate ». Le
        découper en autant d'appels lui ferait manquer celui qu'il ne connaît
        pas."""
        assert mg.resolve_mounts(make_source(), {"addon": "frigate"}) == [
            "nas_config",
            "nas_media",
        ]

    def test_no_target_means_everything(self):
        """Un `repair` sans argument est le geste de quelqu'un qui veut que ça
        reparte, pas qui veut choisir."""
        assert set(mg.resolve_mounts(make_source(), {})) == {"nas_media", "nas_config"}

    def test_an_unknown_mount_is_named(self):
        with pytest.raises(mg.ServiceValidationError, match="Montage inconnu"):
            mg.resolve_mounts(make_source(), {"mount": "parti"})

    def test_an_unwatched_addon_is_named(self):
        with pytest.raises(mg.ServiceValidationError, match="Add-on non surveillé"):
            mg.resolve_mounts(make_source(), {"addon": "core_ssh"})


# --- services -------------------------------------------------------------


class TestRepairService:
    async def test_it_repairs_every_resolved_mount(self):
        source = make_source()
        repaired: list[str] = []

        async def repair(mount):
            repaired.append(mount)

        source.async_repair_now = repair
        await mg.async_repair(make_hass([make_entry(source)]), {"addon": "frigate"})
        assert repaired == ["nas_config", "nas_media"]

    async def test_one_failure_does_not_stop_the_others(self):
        """Un montage en échec ne doit pas empêcher les autres d'être
        réparés."""
        source = make_source()
        seen: list[str] = []

        async def repair(mount):
            seen.append(mount)
            if mount == "nas_config":
                raise RuntimeError("boum")

        source.async_repair_now = repair
        with pytest.raises(mg.HomeAssistantError, match="boum"):
            await mg.async_repair(make_hass([make_entry(source)]), {})
        assert set(seen) == {"nas_media", "nas_config"}

    async def test_without_a_configured_entry_it_says_so(self):
        with pytest.raises(mg.ServiceValidationError, match="n'est pas configuré"):
            await mg.async_repair(make_hass([]), {})


class TestCancelService:
    def test_it_cancels_every_resolved_mount(self):
        source = make_source()
        cancelled: list[str] = []
        source.request_cancel = cancelled.append
        mg.async_cancel(make_hass([make_entry(source)]), {"addon": "motioneye"})
        assert cancelled == ["nas_media"]


class TestSetModeService:
    async def test_it_writes_the_mode_on_the_mount_not_the_addon(self):
        """Un montage est un objet physique unique : il ne peut pas être réparé
        de deux façons parce que deux add-ons l'ont déclaré différemment. Le
        conflit n'est pas arbitré, il est rendu impossible par la forme du
        stockage."""
        source = make_source()
        entry = make_entry(source)
        entry.options = {"mounts": dict(OPTIONS)}
        hass = make_hass([entry])
        hass.config_entries.async_get_entry.return_value = entry
        updates: list = []
        hass.config_entries.async_update_entry = lambda e, **kw: updates.append(kw) or True

        await mg.async_set_mode(hass, {"mount": "nas_media", "mode": "stop_only"})

        written = updates[0]["options"]["mounts"]
        assert written["nas_media"]["mode"] == "stop_only"
        # L'autre montage n'a pas bougé, et le reste de sa configuration non plus.
        assert written["nas_config"]["mode"] == "local_fallback"
        assert written["nas_media"]["host"] == "10.0.0.12"

    async def test_an_unknown_mount_is_refused(self):
        entry = make_entry(make_source())
        entry.options = {"mounts": {}}
        hass = make_hass([entry])
        hass.config_entries.async_get_entry.return_value = entry
        with pytest.raises(mg.ServiceValidationError, match="Montage inconnu"):
            await mg.async_set_mode(hass, {"mount": "nas_media", "mode": "stop_only"})


# --- rechargement ----------------------------------------------------------


class TestUpdateEntryAndEnsureReload:
    def test_a_real_change_leaves_the_listener_do_it(self):
        hass = MagicMock()
        hass.config_entries.async_update_entry.return_value = True
        entry = SimpleNamespace(entry_id="e", update_listeners=[object()])
        mg.update_entry_and_ensure_reload(hass, entry, options={})
        hass.config_entries.async_schedule_reload.assert_not_called()

    def test_an_unchanged_entry_is_reloaded_explicitly(self):
        """Reconfiguration rouverte puis resoumise à l'identique :
        `async_update_entry` renvoie False sans notifier personne, et l'entrée
        resterait en erreur alors que tout vient de rentrer dans l'ordre."""
        hass = MagicMock()
        hass.config_entries.async_update_entry.return_value = False
        entry = SimpleNamespace(entry_id="e", update_listeners=[object()])
        mg.update_entry_and_ensure_reload(hass, entry, options={})
        hass.config_entries.async_schedule_reload.assert_called_once_with("e")

    def test_without_a_listener_it_is_reloaded_explicitly(self):
        """Entrée désactivée, ou setup interrompu avant `add_update_listener`."""
        hass = MagicMock()
        hass.config_entries.async_update_entry.return_value = True
        entry = SimpleNamespace(entry_id="e", update_listeners=[])
        mg.update_entry_and_ensure_reload(hass, entry, options={})
        hass.config_entries.async_schedule_reload.assert_called_once_with("e")


# --- sous-entrées ----------------------------------------------------------


class TestAddonSubentries:
    def test_only_addon_subentries_are_read(self):
        entry = SimpleNamespace(subentries={
            "a": SimpleNamespace(subentry_type="addon",
                                 data={"slug": "frigate", "mounts": ["nas_media"]}),
            "b": SimpleNamespace(subentry_type="autre", data={"slug": "x"}),
        })
        assert mg.addon_subentries(entry) == [{"slug": "frigate", "mounts": ["nas_media"]}]

    def test_they_feed_the_table_directly(self):
        """La sous-entrée et `build_mount_table` doivent parler le même
        vocabulaire, sinon la table se construit vide et l'intégration ne
        surveille rien — sans une ligne de journal."""
        entry = SimpleNamespace(subentries={
            "a": SimpleNamespace(subentry_type="addon",
                                 data={"slug": "frigate", "mounts": ["nas_media"]}),
        })
        table = build_mount_table(OPTIONS, mg.addon_subentries(entry))
        assert table.slugs_for("nas_media") == ("frigate",)


class TestOptionPrecedence:
    def test_option_then_data_then_default(self):
        """L'inverse ferait réafficher la valeur du formulaire initial à chaque
        ouverture des options, et l'utilisateur écraserait son propre réglage
        en validant sans rien toucher."""
        entry = SimpleNamespace(options={"k": 1}, data={"k": 2})
        assert mg.option(entry, "k", 3) == 1
        assert mg.option(SimpleNamespace(options={}, data={"k": 2}), "k", 3) == 2
        assert mg.option(SimpleNamespace(options={}, data={}), "k", 3) == 3


# --- la carte --------------------------------------------------------------


_A_STORE = object()


class Resources:
    def __init__(self, items=(), store=_A_STORE):
        self.loaded = True
        self.store = store
        self._items = list(items)
        self.created: list = []
        self.updated: list = []

    def async_items(self):
        return self._items

    async def async_create_item(self, item):
        self.created.append(item)

    async def async_update_item(self, item_id, changes):
        self.updated.append((item_id, changes))

    async def async_get_info(self):
        self.loaded = True


def hass_with(resources):
    hass = MagicMock()
    hass.data = {"lovelace": SimpleNamespace(resources=resources)}
    return hass


class TestLovelaceResource:
    async def test_it_registers_the_card_once(self):
        resources = Resources()
        assert await mg.async_register_lovelace_resource(hass_with(resources)) is True
        assert resources.created == [{"res_type": "module", "url": mg.CARD_RESOURCE_URL}]

    async def test_an_up_to_date_resource_is_left_alone(self):
        resources = Resources([{"id": "1", "url": mg.CARD_RESOURCE_URL}])
        assert await mg.async_register_lovelace_resource(hass_with(resources)) is True
        assert resources.created == [] and resources.updated == []

    async def test_an_old_version_is_updated_not_duplicated(self):
        """Deux versions du module coexisteraient et la première enregistrée
        gagnerait — donc l'ancienne."""
        resources = Resources([{"id": "1", "url": f"{mg.CARD_URL}?v=0.0.1"}])
        await mg.async_register_lovelace_resource(hass_with(resources))
        assert resources.updated == [("1", {"url": mg.CARD_RESOURCE_URL})]
        assert resources.created == []

    async def test_yaml_mode_falls_back(self):
        """Collection en lecture seule : c'est à l'utilisateur de déclarer la
        ressource, et `_async_setup_card` le lui dit."""
        assert await mg.async_register_lovelace_resource(hass_with(Resources(store=None))) is False

    async def test_a_broken_collection_never_breaks_the_setup(self):
        hass = MagicMock()
        hass.data = {"lovelace": SimpleNamespace(resources=SimpleNamespace(store=object()))}
        assert await mg.async_register_lovelace_resource(hass) is False

    async def test_without_lovelace_it_falls_back(self):
        hass = MagicMock()
        hass.data = {}
        assert await mg.async_register_lovelace_resource(hass) is False


# --- ce que seule la lecture de la source peut vérifier --------------------


class TestTheCoordinatorIsBuiltNotInherited:
    """L'invariant structurant du dépôt. Une classe dérivée d'une base
    MagicMock *est* un MagicMock : elle s'importe, s'instancie, et toutes ses
    méthodes sont muettes. Le jour où quelqu'un écrirait
    `class MountGuardCoordinator(DataUpdateCoordinator)`, la moitié de la suite
    passerait au vert sans rien exécuter."""

    def test_no_module_subclasses_the_coordinator(self):
        component = pathlib.Path(mg.__file__).parent
        for path in component.glob("*.py"):
            source = path.read_text("utf-8")
            assert not re.search(r"class \w+\([^)]*DataUpdateCoordinator", source), path.name

    def test_the_coordinator_is_instantiated_in_setup_entry(self):
        assert "DataUpdateCoordinator(" in SOURCE
        assert "update_method=source.async_update" in SOURCE


class TestRuntimeDataIsActuallyWired:
    """Rien ne fait respecter l'affectation de `runtime_data` : l'attribut n'a
    pas de défaut et son absence est silencieuse — `guard_entries` l'écarte par
    un `getattr`. Ne jamais le poser rendrait l'intégration entièrement muette,
    CI verte."""

    def test_setup_entry_assigns_runtime_data(self):
        assert "entry.runtime_data = MountGuardRuntimeData(" in SOURCE

    def test_the_coordinator_is_published_on_the_source(self):
        """Sans ça, `publish` ne pousserait jamais aux entités : la carte ne se
        mettrait à jour qu'au cycle de polling suivant, une minute plus tard."""
        assert "source.coordinator = coordinator" in SOURCE

    def test_the_supervisor_listener_is_unregistered_on_unload(self):
        """Un écouteur de bus survivant au déchargement continuerait d'appeler
        une source détruite à chaque événement du Superviseur."""
        assert re.search(
            r"entry\.async_on_unload\(\s*hass\.bus\.async_listen\(EVENT_SUPERVISOR", SOURCE
        )


class TestNoAuthenticationPath:
    """Il n'y a rien à authentifier : le Superviseur répond au conteneur core
    sans identifiant, et le NAS n'est joint que par une socket TCP ouverte puis
    refermée. Lever `ConfigEntryAuthFailed` afficherait à l'utilisateur une
    notification « Reconfigurer » devant laquelle il n'aurait rien à saisir.
    C'est la porte que rouvre un copier-coller depuis un autre dépôt."""

    def test_nothing_raises_config_entry_auth_failed(self):
        component = pathlib.Path(mg.__file__).parent
        for path in component.glob("*.py"):
            assert "ConfigEntryAuthFailed" not in path.read_text("utf-8"), path.name

    def test_no_reauth_step_exists(self):
        flow = (pathlib.Path(mg.__file__).parent / "config_flow.py").read_text("utf-8")
        assert "async_step_reauth" not in flow
