"""La séquence complète, jouée bout en bout.

Le seul endroit du dépôt qui arrête des add-ons et déplace des fichiers. Ces
tests le font pour de vrai — vrai système de fichiers temporaire, vraies
étapes, vrai enchaînement — avec un Supervisor simulé et une horloge figée.
Tout ce qui ferait attendre est injecté, donc la suite entière tourne en
quelques centièmes de seconde.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.addon_mount_guard import fileops, repair
from custom_components.addon_mount_guard.models import new_remediation
from custom_components.addon_mount_guard.mount_table import MountConfig, build_mount_table
from custom_components.addon_mount_guard.supervisor_api import SupervisorApiError

T0 = datetime(2026, 9, 20, 18, 0, 0, tzinfo=UTC)


class FakeApi:
    """Supervisor simulé. Retient l'ordre des opérations : c'est lui qui
    distingue une séquence correcte d'une séquence qui arrête après avoir
    déplacé."""

    def __init__(self, slugs=("frigate",), reload_works=True, stop_works=True):
        self.log: list[str] = []
        self.states = dict.fromkeys(slugs, "started")
        self.reload_works = reload_works
        self.stop_works = stop_works
        self.on_reload = None

    async def addon_info(self, slug):
        return SimpleNamespace(
            slug=slug,
            name=slug.title(),
            state=self.states[slug],
            running=self.states[slug] in ("started", "startup"),
        )

    async def stop_addon(self, slug):
        self.log.append(f"stop:{slug}")
        if not self.stop_works:
            return  # le Supervisor accepte, l'add-on ne s'arrête jamais
        self.states[slug] = "stopped"

    async def start_addon(self, slug):
        self.log.append(f"start:{slug}")
        self.states[slug] = "started"

    async def reload_mount(self, name):
        self.log.append(f"reload:{name}")
        if self.on_reload:
            self.on_reload()

    async def mounts(self):
        return []

    async def addons(self):
        return []


@pytest.fixture
def world(tmp_path):
    """Un montage /media/frigate, un add-on, et de quoi piloter /proc/mounts."""
    path = tmp_path / "media" / "frigate"
    path.mkdir(parents=True)
    proc = tmp_path / "proc_mounts"
    proc.write_text("")

    def set_mounted(yes: bool) -> None:
        proc.write_text(f"//nas/media {path} cifs rw 0 0\n" if yes else "")

    table = build_mount_table(
        {"frigate": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "media"}},
        [{"slug": "frigate", "mounts": ["frigate"]}],
    )
    config = MountConfig(
        mount="frigate", path=str(path), host="10.0.0.12", mode="local_fallback",
        usage="media", slugs=("frigate",), overwrite="keep_newest",
    )
    return SimpleNamespace(
        path=path, proc=proc, set_mounted=set_mounted, table=table, config=config
    )


@pytest.fixture(autouse=True)
def proc_mounts(world, monkeypatch):
    """`is_mounted` lit /proc/mounts ; on le pointe vers le fichier du test."""
    real = fileops.is_mounted
    monkeypatch.setattr(
        fileops, "is_mounted", lambda path, _p=None: real(Path(path), world.proc)
    )


def make_runner(api, published=None, **kwargs):
    async def run_executor(func, *args):
        return func(*args)

    async def sleep(_delay):
        await asyncio.sleep(0)

    return repair.RepairRunner(
        api=api,
        run_executor=run_executor,
        publish=(published.append if published is not None else lambda _r: None),
        now=lambda: T0,
        sleep=sleep,
        poll_interval=1.0,
        reload_timeout=3.0,
        stop_timeout=3.0,
        progress_interval=0.001,
        **kwargs,
    )


def make_context(world, states=None, we_stopped=None):
    remediations = states or {"frigate": new_remediation("frigate", str(world.path))}
    return repair.RepairContext(
        table=world.table,
        states=lambda: remediations,
        we_stopped=we_stopped if we_stopped is not None else {},
    )


def pending(world):
    import dataclasses

    return dataclasses.replace(
        new_remediation("frigate", str(world.path)), state="pending"
    )


# --- chemin nominal -----------------------------------------------------


class TestTheHappyPath:
    async def test_the_five_steps_run_in_order(self, world):
        world.set_mounted(False)
        (world.path / "clips").mkdir()
        (world.path / "clips" / "a.mp4").write_text("aaa")
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)
        published: list = []
        runner = make_runner(api, published)

        result = await runner.async_run(world.config, pending(world), make_context(world))

        assert result.state == "ok"
        assert api.log == ["stop:frigate", "reload:frigate", "start:frigate"]
        steps = [r.step for r in published if r.step]
        assert steps[0] == "stopping"
        assert "stashing" in steps and "reloading" in steps and "restoring" in steps
        assert steps[-1] == "starting"

    async def test_the_files_come_back_on_the_share(self, world):
        world.set_mounted(False)
        (world.path / "a.mp4").write_text("aaa")
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)

        await make_runner(api).async_run(world.config, pending(world), make_context(world))

        assert (world.path / "a.mp4").read_text() == "aaa"
        assert not fileops.stash_dir(world.path).exists()

    async def test_the_addon_is_stopped_before_anything_moves(self, world):
        """L'invariant de l'étape 1. Mettre de côté pendant que Frigate écrit
        encore laisse des fichiers à moitié écrits des deux côtés."""
        world.set_mounted(False)
        (world.path / "a.mp4").write_text("aaa")
        api = FakeApi()
        moved_while_running: list[bool] = []

        real_stash = fileops.stash

        def spy(path):
            moved_while_running.append(api.states["frigate"] == "started")
            return real_stash(path)

        api.on_reload = lambda: world.set_mounted(True)
        runner = make_runner(api)
        runner.run_executor = lambda func, *a: _call(spy if func is real_stash else func, *a)

        await runner.async_run(world.config, pending(world), make_context(world))
        assert moved_while_running == [False]

    async def test_the_progress_reaches_the_total(self, world):
        world.set_mounted(False)
        for name in ("a", "b", "c"):
            (world.path / f"{name}.mp4").write_text("xxxxx")
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)

        result = await make_runner(api).async_run(
            world.config, pending(world), make_context(world)
        )
        assert (result.files_done, result.files_total) == (3, 3)
        assert result.bytes_done == 15
        assert result.current_file is None


async def _call(func, *args):
    return func(*args)


# --- rechargement en échec ---------------------------------------------


class TestTheMountDoesNotComeBack:
    async def test_the_files_are_put_back(self, world):
        """Laisser l'add-on redémarrer sur un répertoire vide ressemble à une
        perte de données même quand tout est encore là, à côté."""
        world.set_mounted(False)
        (world.path / "a.mp4").write_text("aaa")
        api = FakeApi()  # on_reload absent : le montage ne revient pas

        result = await make_runner(api).async_run(
            world.config, pending(world), make_context(world)
        )

        assert result.state == "degraded"
        assert (world.path / "a.mp4").read_text() == "aaa"
        assert not fileops.stash_dir(world.path).exists()

    async def test_the_addon_restarts_anyway(self, world):
        """Mode local_fallback : le NAS est absent, l'add-on doit repartir en
        local. Le laisser éteint transformerait une panne de NAS en panne de
        caméra."""
        world.set_mounted(False)
        api = FakeApi()
        await make_runner(api).async_run(world.config, pending(world), make_context(world))
        assert api.log == ["stop:frigate", "reload:frigate", "start:frigate"]

    async def test_a_retry_is_scheduled(self, world):
        world.set_mounted(False)
        result = await make_runner(FakeApi()).async_run(
            world.config, pending(world), make_context(world)
        )
        assert result.next_retry_at is not None
        assert result.last_error


class TestTheAddonWillNotStop:
    async def test_it_fails_instead_of_moving_files(self, world):
        """Le Supervisor rend la main avant l'arrêt effectif. Continuer sur un
        add-on qui écrit encore est précisément ce que l'étape 1 empêche."""
        world.set_mounted(False)
        (world.path / "a.mp4").write_text("aaa")
        api = FakeApi(stop_works=False)

        result = await make_runner(api).async_run(
            world.config, pending(world), make_context(world)
        )

        assert result.state == "degraded"
        assert "reload:frigate" not in api.log
        assert (world.path / "a.mp4").exists()
        assert not fileops.stash_dir(world.path).exists()


class TestAnUnexpectedErrorIsContained:
    async def test_it_becomes_a_degraded_state_not_an_exception(self, world):
        """Une exception qui remonterait ferait échouer le cycle du
        coordinator, donc TOUS les autres montages avec celui-ci."""
        world.set_mounted(False)
        api = FakeApi()

        async def boom(_name):
            raise SupervisorApiError("le Supervisor est parti")

        api.reload_mount = boom
        result = await make_runner(api).async_run(
            world.config, pending(world), make_context(world)
        )
        assert result.state == "degraded"
        assert "Supervisor est parti" in result.last_error

    async def test_the_started_at_of_the_attempt_is_not_lost(self, world):
        """`async_run` n'a plus sous la main que la remédiation d'avant. Y
        repartir effacerait de la carte tout ce que l'utilisateur vient de voir
        défiler."""
        world.set_mounted(False)
        api = FakeApi()

        async def boom(_name):
            raise SupervisorApiError("boum")

        api.reload_mount = boom
        result = await make_runner(api).async_run(
            world.config, pending(world), make_context(world)
        )
        assert result.started_at == T0.isoformat()
        assert any(entry.to == "repairing" for entry in result.history)


# --- reprise et annulation ---------------------------------------------


class TestResume:
    async def test_a_leftover_stash_is_picked_up(self, world):
        """Reprise après un redémarrage de Home Assistant. `_local` est un
        frère du point de montage, donc le bind mount ne le recouvre pas."""
        world.set_mounted(True)
        stashed = fileops.stash_dir(world.path)
        (stashed / "clips").mkdir(parents=True)
        (stashed / "clips" / "a.mp4").write_text("aaa")
        api = FakeApi()

        result = await make_runner(api).async_run(
            world.config, pending(world), make_context(world)
        )

        assert result.state == "ok"
        assert (world.path / "clips" / "a.mp4").read_text() == "aaa"
        assert not stashed.exists()

    async def test_it_always_stops_the_addon_first(self, world):
        """Au redémarrage de Home Assistant, le Supervisor a relancé les
        add-ons. Rapatrier pendant que Frigate écrit dedans annulerait tout le
        bénéfice de l'opération."""
        world.set_mounted(True)
        (fileops.stash_dir(world.path)).mkdir()
        (fileops.stash_dir(world.path) / "a.mp4").write_text("a")
        api = FakeApi()
        await make_runner(api).async_run(world.config, pending(world), make_context(world))
        assert api.log[0] == "stop:frigate"


class TestCancel:
    async def test_before_the_reload_everything_is_put_back(self, world):
        world.set_mounted(False)
        (world.path / "a.mp4").write_text("aaa")
        api = FakeApi()
        runner = make_runner(api)
        api.stop_addon_original = api.stop_addon

        async def stop_then_cancel(slug):
            await api.stop_addon_original(slug)
            runner.request_cancel("frigate")

        api.stop_addon = stop_then_cancel

        result = await runner.async_run(world.config, pending(world), make_context(world))

        assert result.state == "degraded"
        assert result.last_error == repair.CANCELLED
        assert (world.path / "a.mp4").read_text() == "aaa"
        assert "reload:frigate" not in api.log

    async def test_it_still_schedules_a_retry(self, world):
        """L'utilisateur a annulé CETTE tentative, pas la surveillance. Ne rien
        reprogrammer laisserait le montage dégradé pour toujours."""
        world.set_mounted(False)
        api = FakeApi()
        runner = make_runner(api)
        runner.request_cancel("frigate")  # sans effet : rien ne tourne encore

        api.stop_addon_original = api.stop_addon

        async def stop_then_cancel(slug):
            await api.stop_addon_original(slug)
            runner.request_cancel("frigate")

        api.stop_addon = stop_then_cancel
        result = await runner.async_run(world.config, pending(world), make_context(world))
        assert result.next_retry_at is not None

    async def test_a_cancel_on_an_idle_mount_does_nothing(self, world):
        runner = make_runner(FakeApi())
        runner.request_cancel("frigate")
        assert runner.is_running("frigate") is False


# --- add-ons partagés ---------------------------------------------------


class TestSharedAddons:
    @pytest.fixture
    def two_mounts(self, tmp_path, world):
        other = tmp_path / "share" / "config"
        other.mkdir(parents=True)
        table = build_mount_table(
            {
                "frigate": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "media"},
                "config": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "share"},
            },
            [{"slug": "frigate", "mounts": ["frigate", "config"]}],
        )
        world.table = table
        return SimpleNamespace(other=other)

    async def test_a_sibling_awaiting_repair_holds_the_addon(self, two_mounts, world):
        """Le relancer maintenant obligerait à le rearrêter dans la minute, et
        entre les deux il écrirait en local ce qu'on vient de rapatrier."""
        import dataclasses

        world.set_mounted(False)
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)
        states = {
            "frigate": pending(world),
            "config": dataclasses.replace(
                new_remediation("config", str(two_mounts.other)), state="pending"
            ),
        }
        context = make_context(world, states=states, we_stopped={})

        result = await make_runner(api).async_run(world.config, pending(world), context)

        assert "start:frigate" not in api.log
        assert result.addons[0].state == "held"

    async def test_a_degraded_sibling_does_not_hold_it(self, two_mounts, world):
        """Son NAS est absent : l'add-on doit repartir en local. C'est tout
        l'objet de `local_fallback`."""
        import dataclasses

        world.set_mounted(False)
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)
        states = {
            "frigate": pending(world),
            "config": dataclasses.replace(
                new_remediation("config", str(two_mounts.other)), state="degraded"
            ),
        }

        await make_runner(api).async_run(
            world.config, pending(world), make_context(world, states=states)
        )
        assert "start:frigate" in api.log

    async def test_an_addon_the_user_stopped_is_not_restarted(self, world):
        world.set_mounted(False)
        api = FakeApi()
        api.states["frigate"] = "stopped"
        api.on_reload = lambda: world.set_mounted(True)

        await make_runner(api).async_run(world.config, pending(world), make_context(world))
        # Ni arrêté (il l'était déjà) ni relancé : le démarrer en sortie de
        # réparation serait une initiative que rien n'a demandée.
        assert api.log == ["reload:frigate"]


# --- mode stop_only -----------------------------------------------------


class TestStopOnly:
    async def test_it_moves_no_file(self, world):
        """Ce que `stop_only` retire, c'est le déplacement — pas le
        rechargement, sans lequel le montage ne reviendrait jamais."""
        import dataclasses

        world.set_mounted(False)
        (world.path / "a.mp4").write_text("aaa")
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)
        config = dataclasses.replace(world.config, mode="stop_only")

        result = await make_runner(api).async_run(
            config, dataclasses.replace(pending(world), mode="stop_only"), make_context(world)
        )

        assert result.state == "ok"
        assert api.log == ["stop:frigate", "reload:frigate", "start:frigate"]
        assert not fileops.stash_dir(world.path).exists()
        assert (world.path / "a.mp4").read_text() == "aaa"

    async def test_its_stepper_has_three_steps(self, world):
        import dataclasses

        world.set_mounted(False)
        api = FakeApi()
        api.on_reload = lambda: world.set_mounted(True)
        published: list = []
        config = dataclasses.replace(world.config, mode="stop_only")

        await make_runner(api, published).async_run(
            config, dataclasses.replace(pending(world), mode="stop_only"), make_context(world)
        )
        assert {r.step for r in published if r.step} == {"stopping", "reloading", "starting"}
        assert all(r.step_count == 3 for r in published)


# --- concurrence --------------------------------------------------------


class TestConcurrency:
    async def test_a_second_run_on_the_same_mount_is_ignored(self, world):
        """Deux remédiations simultanées sur un même montage se marcheraient
        dessus : l'une met de côté pendant que l'autre recharge."""
        world.set_mounted(False)
        api = FakeApi()
        runner = make_runner(api)
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_reload(_name):
            api.log.append("reload:frigate")
            started.set()
            await release.wait()
            world.set_mounted(True)

        api.reload_mount = slow_reload
        first = asyncio.ensure_future(
            runner.async_run(world.config, pending(world), make_context(world))
        )
        await started.wait()
        second = await runner.async_run(world.config, pending(world), make_context(world))
        assert second.state == "pending"  # rendu tel quel, rien n'a été fait
        release.set()
        assert (await first).state == "ok"
        assert api.log.count("reload:frigate") == 1


class TestAnActiveMountIsNeverStashed:
    """La pire panne que ce module puisse produire : mettre de côté pendant que
    le montage est actif déplacerait le contenu DU NAS vers `<chemin>_local`.
    Le partage serait vidé, la séquence réussirait, et rien ne le signalerait.
    """

    async def test_the_share_content_is_left_alone(self, world):
        world.set_mounted(True)  # reprise après redémarrage : déjà monté
        (world.path / "sur_le_nas.mp4").write_text("nas")
        stashed = fileops.stash_dir(world.path)
        stashed.mkdir()
        (stashed / "local.mp4").write_text("local")

        result = await make_runner(FakeApi()).async_run(
            world.config, pending(world), make_context(world)
        )

        assert result.state == "ok"
        assert (world.path / "sur_le_nas.mp4").read_text() == "nas"
        assert (world.path / "local.mp4").read_text() == "local"
        assert not stashed.exists()

    async def test_no_reload_is_asked_for_a_healthy_mount(self, world):
        """Recharger un partage en bon état, c'est le démonter puis le
        remonter : prendre le risque d'une panne pour confirmer une bonne
        nouvelle."""
        world.set_mounted(True)
        api = FakeApi()
        stashed = fileops.stash_dir(world.path)
        stashed.mkdir()
        (stashed / "a.mp4").write_text("a")

        await make_runner(api).async_run(world.config, pending(world), make_context(world))
        assert "reload:frigate" not in api.log
        assert api.log == ["stop:frigate", "start:frigate"]

    async def test_no_stashing_step_is_published(self, world):
        world.set_mounted(True)
        fileops.stash_dir(world.path).mkdir()
        published: list = []
        await make_runner(FakeApi(), published).async_run(
            world.config, pending(world), make_context(world)
        )
        steps = {r.step for r in published if r.step}
        assert "stashing" not in steps and "reloading" not in steps
