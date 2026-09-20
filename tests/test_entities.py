"""Ce que les entités affichent.

`sensor.py`, `binary_sensor.py` et `button.py` ne sont pas importables sous les
mocks — deux bases MagicMock lèvent `TypeError: metaclass conflict`. Toute leur
logique vit donc ici, et c'est ici qu'elle est testée. Un capteur qui compte mal
ne lève pas : il affiche un chiffre faux, et personne ne le remarque avant d'en
avoir besoin.
"""
from __future__ import annotations

import dataclasses

import pytest

from custom_components.addon_mount_guard import entities
from custom_components.addon_mount_guard.models import RemediationAddon, new_remediation


def rem(mount="nas_media", **changes):
    return dataclasses.replace(new_remediation(mount, f"/media/{mount}"), **changes)


class TestIdentifiers:
    def test_they_derive_from_the_entry_and_a_stable_name(self):
        """Un identifiant qui dépend d'une option signifie qu'en changer crée
        un appareil neuf et orpheline l'ancien, avec son historique et les
        automatisations qui le visaient."""
        assert entities.addon_identifier("e1", "frigate")[1] == "e1_addon_frigate"
        assert entities.mount_identifier("e1", "nas_media")[1] == "e1_mount_nas_media"

    def test_an_addon_and_a_mount_of_the_same_name_do_not_collide(self):
        """Rien n'interdit d'appeler « frigate » à la fois l'add-on et le
        montage — c'est même le cas le plus naturel. Sans le préfixe, les deux
        appareils fusionneraient."""
        assert entities.addon_identifier("e1", "frigate") != entities.mount_identifier(
            "e1", "frigate"
        )


class TestAddonState:
    """L'ordre de précédence dit ce qui mérite d'être affiché quand plusieurs
    choses sont vraies à la fois."""

    def test_a_healthy_addon_is_ok(self):
        states = {"nas_media": rem()}
        assert entities.addon_state(states, "frigate", ["nas_media"]) == "ok"

    def test_a_repair_wins_over_everything(self):
        states = {"nas_media": rem(state="repairing"), "nas_config": rem("nas_config",
                                                                        state="degraded")}
        assert entities.addon_state(states, "f", ["nas_media", "nas_config"]) == "repairing"

    def test_a_pending_mount_already_counts_as_repairing(self):
        """La réparation est décidée : afficher « local » ferait croire que
        rien ne va se passer."""
        states = {"nas_media": rem(state="pending")}
        assert entities.addon_state(states, "f", ["nas_media"]) == "repairing"

    def test_a_stopped_addon_wins_over_local(self):
        """Inverser les deux afficherait « local » sur un add-on arrêté, ce qui
        est faux de la pire façon : rassurant. C'est l'information que
        l'utilisateur cherche quand sa caméra n'enregistre plus."""
        states = {
            "nas_media": rem(
                state="degraded",
                addons=(RemediationAddon("frigate", "Frigate", "stopped"),),
            )
        }
        assert entities.addon_state(states, "frigate", ["nas_media"]) == "stopped"

    def test_a_held_addon_reads_as_stopped(self):
        states = {
            "nas_media": rem(
                state="degraded", addons=(RemediationAddon("frigate", "Frigate", "held"),)
            )
        }
        assert entities.addon_state(states, "frigate", ["nas_media"]) == "stopped"

    def test_a_running_addon_on_a_degraded_mount_is_local(self):
        states = {
            "nas_media": rem(
                state="degraded", addons=(RemediationAddon("frigate", "Frigate", "started"),)
            )
        }
        assert entities.addon_state(states, "frigate", ["nas_media"]) == "local"

    def test_another_addons_state_is_not_read(self):
        """Deux add-ons partagent `nas_media` : l'arrêt de l'un ne doit pas
        s'afficher sur l'autre."""
        states = {
            "nas_media": rem(
                state="degraded",
                addons=(
                    RemediationAddon("frigate", "Frigate", "stopped"),
                    RemediationAddon("motioneye", "MotionEye", "started"),
                ),
            )
        }
        assert entities.addon_state(states, "motioneye", ["nas_media"]) == "local"

    def test_an_addon_without_known_mounts_is_ok(self):
        assert entities.addon_state({}, "frigate", ["parti"]) == "ok"


class TestPendingFiles:
    def test_it_counts_what_is_left_not_the_total(self):
        """Le total ne bougerait pas d'un poil pendant que la barre avance."""
        states = {"nas_media": rem(files_total=100, files_done=40)}
        assert entities.pending_files(states, ["nas_media"]) == 60

    def test_it_adds_up_across_mounts(self):
        states = {
            "nas_media": rem(files_total=10, files_done=4),
            "nas_config": rem("nas_config", files_total=5, files_done=0),
        }
        assert entities.pending_files(states, ["nas_media", "nas_config"]) == 11

    def test_it_never_goes_negative(self):
        """`files_done` peut dépasser le total quand des fichiers apparaissent
        pendant la copie. Un capteur négatif n'a aucun sens."""
        states = {"nas_media": rem(files_total=5, files_done=9)}
        assert entities.pending_files(states, ["nas_media"]) == 0


class TestLastIncident:
    def test_it_takes_the_most_recent(self):
        states = {
            "a": rem("a", last_incident_at="2026-09-20T10:00:00+00:00"),
            "b": rem("b", last_incident_at="2026-09-20T18:00:00+00:00"),
        }
        assert entities.last_incident(states, ["a", "b"]) == "2026-09-20T18:00:00+00:00"

    def test_without_an_incident_it_is_none(self):
        assert entities.last_incident({"a": rem("a")}, ["a"]) is None


class TestProblemAndButtons:
    @pytest.mark.parametrize(
        ("state", "problem"),
        [("ok", False), ("degraded", True), ("pending", True), ("repairing", True)],
    )
    def test_anything_but_ok_is_a_problem(self, state, problem):
        """`pending` compte : le NAS est revenu mais le montage n'est pas
        rétabli, et les add-ons sont retenus à l'arrêt. Le compter sain ferait
        clignoter le capteur au vert au milieu d'une panne."""
        assert entities.has_problem(rem(state=state)) is problem

    def test_an_unknown_mount_is_not_a_problem(self):
        assert entities.has_problem(None) is False

    @pytest.mark.parametrize(
        ("state", "available"),
        [("ok", False), ("degraded", True), ("pending", True), ("repairing", False)],
    )
    def test_the_repair_button_is_available_only_when_useful(self, state, available):
        """Actif sur un montage sain, il arrêterait Frigate pour rien ; actif
        pendant une séquence, il n'aurait rien à lancer."""
        assert entities.repair_available(rem(state=state)) is available

    @pytest.mark.parametrize(
        ("state", "available"),
        [("ok", False), ("degraded", False), ("pending", False), ("repairing", True)],
    )
    def test_cancel_is_available_only_during_a_sequence(self, state, available):
        assert entities.cancel_available(rem(state=state)) is available


class TestActiveRemediations:
    def test_it_counts_pending_and_repairing(self):
        """`pending` compte : l'exclure ferait retomber le compteur à zéro
        entre deux montages d'un même add-on qui se réparent l'un après
        l'autre, et une automatisation branchée dessus croirait que tout est
        fini."""
        states = {
            "a": rem("a", state="repairing"),
            "b": rem("b", state="pending"),
            "c": rem("c", state="degraded"),
            "d": rem("d"),
        }
        assert entities.active_remediations(states) == 2

    def test_nothing_running_is_zero(self):
        assert entities.active_remediations({"a": rem("a", state="degraded")}) == 0


class TestThePlatformsStayThin:
    """Le jour où une dérivation retourne dans `sensor.py`, elle devient
    invisible à cette suite sans que rien ne le signale. Ces deux gardes
    rendent le glissement visible."""

    PLATFORMS = ("sensor", "binary_sensor", "button", "websocket_api")

    def _source(self, name):
        import pathlib

        import custom_components.addon_mount_guard as mg

        return (pathlib.Path(mg.__file__).parent / f"{name}.py").read_text("utf-8")

    def test_no_platform_imports_the_decision_modules(self):
        """`machine` et `fileops` décident et agissent. Les voir apparaître
        dans une plateforme signifie qu'une décision vient d'échapper aux
        tests."""
        for name in self.PLATFORMS:
            source = self._source(name)
            for forbidden in ("from .machine import", "from .fileops import",
                              "from .repair import", "from . import machine",
                              "from . import fileops"):
                assert forbidden not in source, f"{name} : {forbidden}"

    def test_the_entity_platforms_take_their_logic_from_entities(self):
        for name in ("sensor", "binary_sensor", "button"):
            assert "from .entities import" in self._source(name), name

    def test_the_websocket_only_forwards(self):
        """Il pousse `to_wire` tel quel. Composer un payload différent du
        capteur ferait diverger les deux chemins que la carte lit, et le repli
        sur l'attribut afficherait autre chose que la souscription."""
        source = self._source("websocket_api")
        assert "to_wire" in source
        assert "source.subscribe(" in source
