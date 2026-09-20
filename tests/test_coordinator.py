"""Le cycle de surveillance : ce qu'il constate et ce qu'il décide.

Rien n'hérite ici, et c'est la condition pour que ces tests existent : sous les
mocks de `conftest.py`, une classe dérivée d'une base MagicMock *est* un
MagicMock — elle s'importe, s'instancie, et toutes ses méthodes sont muettes.
`TestNothingInherits` verrouille ça.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.addon_mount_guard import coordinator as mod
from custom_components.addon_mount_guard import fileops
from custom_components.addon_mount_guard.models import new_remediation, to_wire
from custom_components.addon_mount_guard.supervisor_api import SupervisorApiError

T0 = datetime(2026, 9, 20, 18, 0, 0, tzinfo=UTC)

OPTIONS = {"frigate": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "media"}}
SUBENTRIES = [{"slug": "frigate", "mounts": ["frigate"]}]


class FakeStore:
    def __init__(self, data=None):
        self.data = data
        self.saved: list = []

    async def async_load(self):
        return self.data

    def async_delay_save(self, snapshot, _delay):
        self.saved.append(snapshot())


class FakeRunner:
    def __init__(self):
        self.runs: list[str] = []
        self.stops: list[str] = []
        self.cancels: list[str] = []
        self.running: set[str] = set()

    def is_running(self, mount):
        return mount in self.running

    def request_cancel(self, mount):
        self.cancels.append(mount)

    async def async_run(self, config, remediation, context):
        self.runs.append(config.mount)
        return dataclasses.replace(remediation, state="ok")

    async def async_stop_addons(self, config, remediation, context):
        self.stops.append(config.mount)
        return remediation


class FakeApi:
    def __init__(self, mounts=None, addons=None, error=None):
        self._mounts = mounts if mounts is not None else [
            SimpleNamespace(name="frigate", usage="media", type="cifs", state="failed")
        ]
        self._addons = addons if addons is not None else [
            SimpleNamespace(slug="frigate", name="Frigate", state="started", running=True)
        ]
        self._error = error

    async def mounts(self):
        if self._error:
            raise self._error
        return self._mounts

    async def addons(self):
        if self._error:
            raise self._error
        return self._addons


@pytest.fixture
def world(tmp_path, monkeypatch):
    path = tmp_path / "media" / "frigate"
    path.mkdir(parents=True)
    proc = tmp_path / "proc_mounts"
    proc.write_text("")

    def set_mounted(yes):
        proc.write_text(f"//nas/media {path} cifs rw 0 0\n" if yes else "")

    real = fileops.is_mounted
    monkeypatch.setattr(fileops, "is_mounted", lambda p, _x=None: real(Path(p), proc))
    monkeypatch.setattr(mod.dt_util, "utcnow", lambda: T0)
    monkeypatch.setattr(mod, "async_is_reachable", _reachable(False))

    OPTIONS["frigate"]["usage"] = "media"
    return SimpleNamespace(path=path, set_mounted=set_mounted, tmp=tmp_path)


def _reachable(value):
    async def probe(host, *, port, **_kwargs):
        return value

    return probe


def make_source(world, api=None, runner=None, store=None, **kwargs):
    hass = MagicMock()
    hass.async_add_executor_job = _executor
    fired: list = []
    hass.bus.async_fire = lambda event, data: fired.append((event, data))
    tasks: list = []
    hass.async_create_task = tasks.append

    source = mod.MountGuardDataSource(
        hass,
        api or FakeApi(),
        runner or FakeRunner(),
        store or FakeStore(),
        **kwargs,
    )
    # Le chemin réel du montage est celui du répertoire temporaire.
    options = {"frigate": {**OPTIONS["frigate"], "usage": "media"}}
    source.rebuild_table(options, SUBENTRIES)
    config = source.table.mounts["frigate"]
    source._table.mounts["frigate"] = dataclasses.replace(config, path=str(world.path))
    source._states["frigate"] = new_remediation("frigate", str(world.path))
    source.fired = fired
    source.tasks = tasks
    return source


async def _executor(func, *args):
    return func(*args)


# --- l'invariant structurant --------------------------------------------


class TestNothingInherits:
    """Si `MountGuardDataSource` dérivait un jour de `DataUpdateCoordinator`,
    il deviendrait un MagicMock sous les mocks : instanciable, muet, et TOUS
    les tests de ce fichier passeraient au vert sans rien exécuter."""

    def test_the_source_is_a_real_class(self):
        assert isinstance(mod.MountGuardDataSource, type)
        assert mod.MountGuardDataSource.__bases__ == (object,)

    def test_its_methods_really_run(self):
        source = mod.MountGuardDataSource(MagicMock(), FakeApi(), FakeRunner(), FakeStore())
        source.rebuild_table(OPTIONS, SUBENTRIES)
        assert set(source.table.mounts) == {"frigate"}


# --- table et ménage -----------------------------------------------------


class TestRebuildTable:
    def test_a_removed_mount_is_forgotten(self, world):
        """Le garder ferait afficher indéfiniment sur la carte un montage que
        l'utilisateur vient justement de retirer."""
        source = make_source(world)
        source.rebuild_table({}, [])
        assert source._states == {}

    def test_a_mode_change_reaches_the_existing_state(self, world):
        source = make_source(world)
        source.rebuild_table(
            {"frigate": {**OPTIONS["frigate"], "mode": "stop_only"}}, SUBENTRIES
        )
        assert source._states["frigate"].mode == "stop_only"
        assert source._states["frigate"].step_count == 3


# --- le cycle ------------------------------------------------------------


class TestTheCycle:
    async def test_a_lost_mount_degrades(self, world):
        world.set_mounted(False)
        source = make_source(world)
        states = await source.async_update()
        assert states["frigate"].state == "degraded"

    async def test_a_healthy_mount_stays_ok_and_is_not_probed(self, world):
        """Ouvrir une connexion TCP vers le NAS toutes les soixante secondes
        pour un montage en bon état est gratuit pour nous et pas pour lui."""
        world.set_mounted(True)
        probed: list = []

        async def probe(host, *, port, **_kwargs):
            probed.append(host)
            return True

        source = make_source(world)
        mod.async_is_reachable = probe
        try:
            states = await source.async_update()
        finally:
            mod.async_is_reachable = _reachable(False)
        assert states["frigate"].state == "ok"
        assert probed == []

    async def test_a_reachable_nas_makes_it_pending_and_launches_a_repair(
        self, world, monkeypatch
    ):
        world.set_mounted(False)
        monkeypatch.setattr(mod, "async_is_reachable", _reachable(True))
        source = make_source(world)
        source._states["frigate"] = dataclasses.replace(
            source._states["frigate"], state="degraded"
        )
        states = await source.async_update()
        assert states["frigate"].state == "pending"
        assert len(source.tasks) == 1
        for task in source.tasks:
            await task

    async def test_a_running_repair_is_left_alone(self, world):
        """Un relevé arrivé au milieu de l'étape 3 verrait un montage absent
        que la séquence vient elle-même de recharger."""
        world.set_mounted(False)
        runner = FakeRunner()
        runner.running.add("frigate")
        source = make_source(world, runner=runner)
        states = await source.async_update()
        assert states["frigate"].state == "ok"  # inchangé, non observé

    async def test_a_dead_supervisor_fails_the_cycle(self, world):
        """Un Supervisor injoignable n'est pas une panne de montage : il faut
        que les entités passent en « indisponible » plutôt que d'annoncer un
        état qu'on n'a pas relevé."""
        source = make_source(world, api=FakeApi(error=SupervisorApiError("mort")))
        with pytest.raises(mod.UpdateFailed):
            await source.async_update()


class TestStashedFilesAreSeen:
    async def test_leftovers_trigger_a_repair_even_on_a_mounted_share(
        self, world, monkeypatch
    ):
        """La reprise après redémarrage, vue depuis le cycle ordinaire."""
        world.set_mounted(True)
        fileops.stash_dir(world.path).mkdir()
        monkeypatch.setattr(mod, "async_is_reachable", _reachable(True))
        source = make_source(world)
        states = await source.async_update()
        assert states["frigate"].state == "pending"
        for task in source.tasks:
            await task


# --- add-ons -------------------------------------------------------------


class TestAddonStates:
    async def test_a_running_addon_is_reported_started(self, world):
        world.set_mounted(True)
        source = make_source(world)
        states = await source.async_update()
        assert states["frigate"].addons[0].state == "started"
        assert states["frigate"].addons[0].name == "Frigate"

    async def test_an_addon_held_by_another_mount_keeps_saying_so(self, world, monkeypatch):
        """Sans cette dérivation à chaque cycle, un add-on maintenu arrêté
        repasserait à « arrêté » au premier relevé, et la carte cesserait
        d'expliquer pourquoi il ne tourne pas."""
        world.set_mounted(True)
        other = world.tmp / "share" / "config"
        other.mkdir(parents=True)
        source = make_source(world)
        source.rebuild_table(
            {
                "frigate": {**OPTIONS["frigate"], "usage": "media"},
                "config": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "share"},
            },
            [{"slug": "frigate", "mounts": ["frigate", "config"]}],
        )
        source._table.mounts["frigate"] = dataclasses.replace(
            source._table.mounts["frigate"], path=str(world.path)
        )
        source._table.mounts["config"] = dataclasses.replace(
            source._table.mounts["config"], path=str(other)
        )
        source._states["config"] = dataclasses.replace(
            new_remediation("config", str(other)), state="pending"
        )
        api = FakeApi(
            mounts=[SimpleNamespace(name="frigate", usage="media", type="cifs", state="active")],
            addons=[SimpleNamespace(slug="frigate", name="Frigate", state="stopped",
                                    running=False)],
        )
        source.api = api
        states = await source.async_update()
        assert states["frigate"].addons[0].state == "held"


# --- publication ---------------------------------------------------------


class TestPublish:
    def test_every_channel_gets_the_same_payload(self, world):
        """Un seul chemin : les trois canaux ne peuvent pas diverger, et un
        champ ajouté au contrat arrive partout sans rien toucher."""
        source = make_source(world)
        seen: list = []
        source.subscribe(seen.append)
        remediation = dataclasses.replace(
            source._states["frigate"], state="degraded", last_error="boum"
        )
        source.publish(remediation)
        assert seen == [to_wire(remediation)]
        assert source.fired[0][0].endswith("_event")
        assert source.fired[0][1]["to"] == "degraded"

    def test_no_event_without_a_state_change(self, world):
        """La progression d'un rapatriement publie une douzaine de fois en deux
        minutes. Un événement par publication noierait les automatisations."""
        source = make_source(world)
        current = source._states["frigate"]
        source.publish(dataclasses.replace(current, files_done=1))
        source.publish(dataclasses.replace(current, files_done=2))
        assert source.fired == []

    def test_a_failing_subscriber_does_not_stop_the_remediation(self, world):
        """Connexion WebSocket fermée entre-temps : la séquence en cours ne
        doit pas s'interrompre pour autant."""
        source = make_source(world)
        source.subscribe(lambda _payload: 1 / 0)
        seen: list = []
        source.subscribe(seen.append)
        source.publish(dataclasses.replace(source._states["frigate"], state="degraded"))
        assert len(seen) == 1

    def test_unsubscribing_works(self, world):
        source = make_source(world)
        seen: list = []
        unsubscribe = source.subscribe(seen.append)
        unsubscribe()
        source.publish(dataclasses.replace(source._states["frigate"], state="degraded"))
        assert seen == []


# --- persistance ---------------------------------------------------------


class TestPersistence:
    async def test_an_interrupted_repair_comes_back_as_pending(self, world):
        """`repairing` empêcherait `observe` de le regarder : il resterait figé
        pour toujours, ses add-ons arrêtés avec lui."""
        store = FakeStore({
            "mounts": {"frigate": {"mount": "frigate", "path": str(world.path),
                                   "state": "repairing", "step": "restoring"}},
            "we_stopped": {"frigate": True},
        })
        source = make_source(world, store=store)
        await source.async_load()
        assert source._states["frigate"].state == "pending"
        assert source._states["frigate"].step is None
        assert source._we_stopped == {"frigate": True}

    async def test_who_we_stopped_survives_a_restart(self, world):
        """Sans cette mémoire, on ne saurait plus qui relancer — et on
        démarrerait un add-on que l'utilisateur avait arrêté lui-même."""
        store = FakeStore({"we_stopped": {"frigate": True, "autre": False}})
        source = make_source(world, store=store)
        await source.async_load()
        assert source._we_stopped["frigate"] is True

    async def test_an_unreadable_payload_does_not_stop_the_load(self, world):
        store = FakeStore({"mounts": {"frigate": {"pas": "exploitable"}}})
        source = make_source(world, store=store)
        await source.async_load()  # ne lève pas
        assert source._states["frigate"].state == "ok"

    def test_saving_is_delayed(self, world):
        """Une remédiation publie une douzaine de fois en deux minutes :
        écrire à chaque fois userait la carte SD pour un état qu'on relit une
        seule fois, au démarrage."""
        store = FakeStore()
        source = make_source(world, store=store)
        source.publish(dataclasses.replace(source._states["frigate"], state="degraded"))
        assert store.saved[-1]["mounts"]["frigate"]["state"] == "degraded"


# --- réactions -----------------------------------------------------------


class TestReactions:
    async def test_stop_only_stops_at_once_without_waiting_for_the_nas(self, world):
        """Étape 1 dès la panne : c'est tout ce que ce mode promet."""
        world.set_mounted(False)
        runner = FakeRunner()
        source = make_source(world, runner=runner)
        source.rebuild_table(
            {"frigate": {**OPTIONS["frigate"], "mode": "stop_only"}}, SUBENTRIES
        )
        source._table.mounts["frigate"] = dataclasses.replace(
            source._table.mounts["frigate"], path=str(world.path)
        )
        await source.async_update()
        assert runner.stops == ["frigate"]

    async def test_the_disk_guard_stops_the_addons(self, world, monkeypatch):
        world.set_mounted(False)
        monkeypatch.setattr(fileops, "free_ratio", lambda _p: 0.02)
        runner = FakeRunner()
        source = make_source(world, runner=runner, min_free_ratio=0.10)
        source._states["frigate"] = dataclasses.replace(
            source._states["frigate"], state="degraded"
        )
        await source.async_update()
        assert runner.stops == ["frigate"]

    async def test_a_healthy_disk_stops_nothing(self, world, monkeypatch):
        world.set_mounted(False)
        monkeypatch.setattr(fileops, "free_ratio", lambda _p: 0.80)
        runner = FakeRunner()
        source = make_source(world, runner=runner, min_free_ratio=0.10)
        source._states["frigate"] = dataclasses.replace(
            source._states["frigate"], state="degraded"
        )
        await source.async_update()
        assert runner.stops == []

    async def test_repair_now_clears_the_backoff(self, world):
        """Contrepartie du choix fait dans `_fail` : celui qui veut relancer
        tout de suite a ce bouton, celui qui ne fait rien n'est pas
        abandonné."""
        runner = FakeRunner()
        source = make_source(world, runner=runner)
        source._states["frigate"] = dataclasses.replace(
            source._states["frigate"], state="degraded", next_retry_at="2099-01-01T00:00:00+00:00"
        )
        await source.async_repair_now("frigate")
        assert runner.runs == ["frigate"]

    async def test_repair_on_an_unknown_mount_says_so(self, world):
        source = make_source(world)
        with pytest.raises(ValueError, match="Montage inconnu"):
            await source.async_repair_now("nexiste_pas")


class TestSupervisorEvents:
    async def test_a_mount_failure_triggers_a_refresh(self, world):
        source = make_source(world)
        source.coordinator = MagicMock()
        refreshed: list = []

        async def refresh():
            refreshed.append(True)

        source.coordinator.async_request_refresh = refresh
        await source.async_handle_supervisor_event(
            SimpleNamespace(data={"event": "issue_changed",
                                  "data": {"type": "mount_failed", "reference": "frigate"}})
        )
        assert refreshed == [True]

    @pytest.mark.parametrize("data", [
        {"event": "supervisor_update"},
        {"event": "issue_changed", "data": {"type": "free_space"}},
        {"event": "issue_changed", "data": {"type": "mount_failed", "reference": "autre"}},
    ])
    async def test_anything_else_is_ignored(self, world, data):
        """Un rafraîchissement par événement du Supervisor, c'est un relevé
        complet — sondes TCP comprises — à chaque redémarrage d'add-on."""
        source = make_source(world)
        source.coordinator = MagicMock()
        called: list = []

        async def refresh():
            called.append(True)

        source.coordinator.async_request_refresh = refresh
        await source.async_handle_supervisor_event(SimpleNamespace(data=data))
        assert called == []


def test_unique_ids_derive_from_the_entry_not_an_option():
    """Un identifiant qui dépend d'un réglage signifie qu'en changer crée des
    entités neuves et orpheline les anciennes : tableau de bord cassé,
    historique perdu, automatisations muettes."""
    assert mod.build_unique_id("abc123", "frigate", "state") == "abc123_frigate_state"
