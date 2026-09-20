"""La seule porte vers le Supervisor.

Ce qui est testé ici n'est pas le Supervisor — on n'en a pas — mais la
traduction de ses modèles vers les nôtres, et la remise en forme de ses pannes.
C'est la couture par laquelle toute la séquence de réparation devient testable,
et le seul endroit à corriger le jour où l'amont change.
"""
from __future__ import annotations

from pathlib import PurePath
from types import SimpleNamespace

import pytest
from aiohasupervisor.exceptions import SupervisorError as LibSupervisorError

from custom_components.addon_mount_guard.supervisor_api import (
    HassioSupervisorApi,
    SupervisorApiError,
)


class FakeEnum(str):
    """Un StrEnum se comporte comme une chaîne, et c'est ce dont on dépend :
    `_text` doit rendre « media » et non « MountUsage.MEDIA »."""


def mount_response(name, usage="media", type_="cifs", state="active", user_path=None):
    return SimpleNamespace(
        name=name,
        usage=FakeEnum(usage),
        type=FakeEnum(type_),
        state=FakeEnum(state) if state is not None else None,
        server="10.0.0.12",
        user_path=PurePath(user_path) if user_path else None,
    )


def addon_response(slug, name="Frigate", state="started"):
    return SimpleNamespace(slug=slug, name=name, state=FakeEnum(state))


class FakeClient:
    """Double du client officiel : retient les appels, rend ce qu'on lui dit."""

    def __init__(self, mounts=(), addons=(), error=None):
        self.calls: list[str] = []
        self._mounts = list(mounts)
        self._addons = list(addons)
        self._error = error
        self.mounts = SimpleNamespace(info=self._info, reload_mount=self._reload)
        self.addons = SimpleNamespace(
            list=self._list,
            addon_info=self._addon_info,
            start_addon=self._start,
            stop_addon=self._stop,
        )

    async def _raise_if_asked(self):
        if self._error:
            raise self._error

    async def _info(self):
        self.calls.append("mounts.info")
        await self._raise_if_asked()
        return SimpleNamespace(mounts=self._mounts, default_backup_mount=None)

    async def _reload(self, name):
        self.calls.append(f"reload:{name}")
        await self._raise_if_asked()

    async def _list(self):
        self.calls.append("addons.list")
        await self._raise_if_asked()
        return self._addons

    async def _addon_info(self, slug):
        self.calls.append(f"info:{slug}")
        await self._raise_if_asked()
        return next(a for a in self._addons if a.slug == slug)

    async def _start(self, slug):
        self.calls.append(f"start:{slug}")
        await self._raise_if_asked()

    async def _stop(self, slug):
        self.calls.append(f"stop:{slug}")
        await self._raise_if_asked()


class TestMounts:
    async def test_the_enums_become_plain_strings(self):
        """Tout le reste du dépôt compare des chaînes. Laisser passer un
        StrEnum marcherait par accident aujourd'hui et cesserait le jour où
        l'amont en fait un IntEnum ou une dataclasse."""
        api = HassioSupervisorApi(FakeClient(mounts=[mount_response("nas_media")]))
        mount = (await api.mounts())[0]
        assert mount.usage == "media"
        assert type(mount.usage) is str
        assert mount.type == "cifs"

    async def test_an_inactive_mount_keeps_a_none_state(self):
        """Un montage jamais activé n'a pas d'état. Le traduire en chaîne
        « None » le ferait comparer à un état réel, et `active` répondrait
        n'importe quoi."""
        api = HassioSupervisorApi(FakeClient(mounts=[mount_response("m", state=None)]))
        mount = (await api.mounts())[0]
        assert mount.state is None
        assert mount.active is False

    async def test_backup_is_flagged_unsupported(self):
        """Le flux de configuration s'en sert pour refuser la saisie :
        `/backup` n'a pas de <nom> dans son chemin, donc la mise de côté
        écrirait `/backup_local` à la racine du conteneur."""
        api = HassioSupervisorApi(
            FakeClient(mounts=[mount_response("m", usage="media"),
                               mount_response("b", usage="backup")])
        )
        by_name = {m.name: m for m in await api.mounts()}
        assert by_name["m"].supported is True
        assert by_name["b"].supported is False

    async def test_the_user_path_is_carried_as_a_string(self):
        """Gardé pour recouper notre propre dérivation : deux façons
        indépendantes d'obtenir le même chemin, dont le désaccord signalerait
        que le Supervisor a changé sa disposition."""
        api = HassioSupervisorApi(
            FakeClient(mounts=[mount_response("nas_media", user_path="/media/nas_media")])
        )
        assert (await api.mounts())[0].user_path == "/media/nas_media"

    async def test_reload_reaches_the_right_endpoint(self):
        client = FakeClient()
        await HassioSupervisorApi(client).reload_mount("nas_media")
        assert client.calls == ["reload:nas_media"]


class TestAddons:
    async def test_a_starting_addon_counts_as_running(self):
        """LE piège de l'étape 1. Un add-on en `startup` n'est pas arrêté :
        l'oublier ferait croire l'arrêt terminé alors que Frigate ouvre
        justement ses fichiers, et la mise de côté partirait sous ses pieds."""
        api = HassioSupervisorApi(FakeClient(addons=[addon_response("f", state="startup")]))
        assert (await api.addons())[0].running is True

    @pytest.mark.parametrize("state", ["stopped", "unknown", "error"])
    async def test_everything_else_counts_as_stopped(self, state):
        api = HassioSupervisorApi(FakeClient(addons=[addon_response("f", state=state)]))
        assert (await api.addons())[0].running is False

    async def test_a_missing_name_falls_back_to_the_slug(self):
        """Add-on dont le dépôt a disparu. Le slug est moins beau qu'un nom, et
        infiniment plus utile qu'une case vide sur la carte."""
        api = HassioSupervisorApi(FakeClient(addons=[addon_response("f", name=None)]))
        assert (await api.addon_info("f")).name == "f"

    async def test_start_and_stop_reach_the_right_endpoints(self):
        client = FakeClient()
        api = HassioSupervisorApi(client)
        await api.stop_addon("frigate")
        await api.start_addon("frigate")
        assert client.calls == ["stop:frigate", "start:frigate"]


class TestFailuresAreWrapped:
    """Un seul type à rattraper chez l'appelant, quelle que soit l'exception
    que l'amont choisira de lever la prochaine fois."""

    async def test_a_library_error_is_named(self):
        api = HassioSupervisorApi(FakeClient(error=LibSupervisorError("hors service")))
        with pytest.raises(SupervisorApiError, match=r"mounts\.info"):
            await api.mounts()

    async def test_anything_else_is_wrapped_too(self):
        """Une panne de transport ne doit pas remonter telle quelle dans le
        coordinator : elle y ferait échouer le cycle entier au lieu du seul
        montage concerné."""
        api = HassioSupervisorApi(FakeClient(error=RuntimeError("boum")))
        with pytest.raises(SupervisorApiError, match="boum"):
            await api.addons()

    async def test_the_failing_operation_is_named_in_the_message(self):
        """C'est ce qui distingue « le Supervisor est mort » de « cet add-on
        n'existe plus » dans le journal, sans avoir à remonter la pile."""
        api = HassioSupervisorApi(FakeClient(error=LibSupervisorError("404")))
        with pytest.raises(SupervisorApiError, match=r"stop_addon\(frigate\)"):
            await api.stop_addon("frigate")
