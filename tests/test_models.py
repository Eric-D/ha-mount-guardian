"""Le contrat Python et son miroir TypeScript doivent rester alignés.

Rien d'autre ne relie `models.py` à `frontend/src/types.ts` : deux langages,
deux outillages, deux CI. Un champ ajouté d'un côté et oublié de l'autre ne
casse ni `ruff`, ni `tsc`, ni un rendu — la carte affiche simplement `undefined`
là où elle attendait une valeur, ou ignore en silence l'information qu'on vient
d'ajouter pour elle.

Cette suite croise donc les clés émises et les littéraux des unions. Elle porte
sur les noms **de sortie** (`to_wire`), pas sur les attributs Python : `from_`
est émis `from`, parce que `from` est un mot-clé Python et pas un mot-clé
JavaScript.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re

from custom_components.addon_mount_guard import models
from custom_components.addon_mount_guard.models import HISTORY_LENGTH

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPES_TS = (ROOT / "frontend/src/types.ts").read_text("utf-8")


def _strip_comments(source: str) -> str:
    """Les commentaires JSDoc contiennent des « mot: » qui passeraient pour des
    champs. Les retirer avant toute analyse, plutôt que raffiner le motif."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


TYPES_CLEAN = _strip_comments(TYPES_TS)


def ts_interface_keys(name: str) -> tuple[str, ...]:
    """Clés déclarées par une interface TypeScript, dans l'ordre du fichier."""
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", TYPES_CLEAN, re.DOTALL)
    assert match, f"interface {name} introuvable dans types.ts"
    return tuple(re.findall(r"^\s*(\w+)\??:", match.group(1), re.MULTILINE))


def ts_union_members(name: str) -> tuple[str, ...]:
    """Littéraux d'une union de chaînes TypeScript, dans l'ordre du fichier."""
    match = re.search(rf"export type {name} =(.*?);", TYPES_CLEAN, re.DOTALL)
    assert match, f"union {name} introuvable dans types.ts"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


PAIRS = (
    (models.Remediation, "Remediation"),
    (models.RemediationAddon, "RemediationAddon"),
    (models.RemediationTransition, "RemediationTransition"),
)

UNIONS = (
    (models.MOUNT_STATES, "MountState"),
    (models.MODES, "Mode"),
    (models.STEPS, "Step"),
    (models.ADDON_STATES, "AddonState"),
)


class TestTheContractIsMirrored:
    def test_every_dataclass_has_the_same_keys_in_typescript(self):
        for cls, name in PAIRS:
            assert models.wire_keys(cls) == ts_interface_keys(name), name

    def test_every_union_has_the_same_members_in_typescript(self):
        for members, name in UNIONS:
            assert members == ts_union_members(name), name

    def test_the_python_keyword_is_renamed_on_the_wire(self):
        """`from` est un mot-clé Python et pas un mot-clé JavaScript. Le
        renommage est porté par la métadonnée du champ ; le supprimer en
        croyant simplifier émettrait `from_`, que la carte lirait `undefined`
        sur toutes les lignes d'historique."""
        assert "from_" not in models.wire_keys(models.RemediationTransition)
        assert "from" in models.wire_keys(models.RemediationTransition)


class TestStepCountCannotLie:
    """Le nombre d'étapes est une propriété du mode, pas une donnée libre."""

    def test_it_follows_the_mode_at_construction(self):
        assert models.new_remediation("m", "/media/m", "local_fallback").step_count == 5
        assert models.new_remediation("m", "/media/m", "stop_only").step_count == 3

    def test_it_follows_the_mode_after_a_replace(self):
        """C'est le chemin réel : `set_mode` fait un `replace`. Sans le recalage
        de `__post_init__`, la carte dessinerait cinq cases pour une séquence
        qui en fait deux."""
        base = models.new_remediation("m", "/media/m", "local_fallback")
        assert dataclasses.replace(base, mode="stop_only").step_count == 3

    def test_every_mode_declares_its_sequence(self):
        assert set(models.STEPS_BY_MODE) == set(models.MODES)

    def test_every_numbered_step_belongs_to_the_vocabulary(self):
        for sequence in models.STEPS_BY_MODE.values():
            assert set(sequence) <= set(models.STEPS)


class TestStepIndex:
    def test_outside_a_sequence_it_is_zero(self):
        """0 distingue « pas commencé » de la première étape, qui vaut 1."""
        assert models.step_index_of("local_fallback", None) == 0

    def test_it_is_one_based(self):
        assert models.step_index_of("local_fallback", "stopping") == 1
        assert models.step_index_of("local_fallback", "starting") == 5

    def test_rollback_takes_the_rank_of_the_step_it_replaces(self):
        """`rolling_back` est l'échec de `restoring`, pas une sixième étape :
        lui donner un rang de plus ferait déborder le stepper."""
        assert models.step_index_of("local_fallback", "rolling_back") == models.step_index_of(
            "local_fallback", "restoring"
        )

    def test_stop_only_numbers_only_its_own_steps(self):
        assert models.step_index_of("stop_only", "stopping") == 1
        assert models.step_index_of("stop_only", "starting") == 3
        # `stashing` n'existe pas dans cette séquence : 0 plutôt qu'une
        # exception, pour qu'un changement de mode en cours de route n'arrête
        # pas la remédiation sur un KeyError.
        assert models.step_index_of("stop_only", "stashing") == 0


class TestNeedsRemediation:
    """Le prédicat dont dépend la relance des add-ons partagés."""

    def test_a_degraded_mount_does_not_hold_its_addons(self):
        """LE point à ne pas défaire. Un montage dégradé dont le NAS est
        toujours absent est un repli assumé : ses add-ons doivent tourner en
        local. Répondre oui ici laisserait un add-on arrêté aussi longtemps que
        le second NAS resterait éteint, ce qui vide `local_fallback` de son
        sens."""
        base = models.new_remediation("m", "/media/m")
        assert models.needs_remediation(dataclasses.replace(base, state="degraded")) is False

    def test_a_healthy_mount_does_not_hold_its_addons(self):
        base = models.new_remediation("m", "/media/m")
        assert models.needs_remediation(base) is False

    def test_a_pending_or_repairing_mount_holds_them(self):
        base = models.new_remediation("m", "/media/m")
        for state in ("pending", "repairing"):
            assert models.needs_remediation(dataclasses.replace(base, state=state)) is True

    def test_the_vocabulary_is_partitioned(self):
        """Un état qui ne serait ni actionnable ni au repos n'aurait pas de
        réponse ici, et la relance dépendrait de l'ordre des tests."""
        assert set(models.ACTIONABLE_STATES) < set(models.MOUNT_STATES)


class TestSerialisation:
    def test_nested_dataclasses_are_serialised(self):
        remediation = dataclasses.replace(
            models.new_remediation("nas_media", "/media/frigate"),
            addons=(models.RemediationAddon("ccab4aaf_frigate", "Frigate", "held"),),
            history=(
                models.RemediationTransition(
                    at="2026-09-20T18:44:11+00:00", from_="ok", to="degraded"
                ),
            ),
        )
        wire = models.to_wire(remediation)
        assert wire["addons"] == [
            {"slug": "ccab4aaf_frigate", "name": "Frigate", "state": "held"}
        ]
        assert wire["history"][0]["from"] == "ok"

    def test_tuples_become_lists(self):
        """Un tuple n'est pas sérialisable en JSON par le WebSocket de Home
        Assistant, et l'attribut d'entité le rendrait en chaîne."""
        wire = models.to_wire(models.new_remediation("m", "/media/m"))
        assert isinstance(wire["addons"], list)
        assert isinstance(wire["history"], list)


class TestFromWire:
    """Relecture de l'état persisté. Le `Store` versionne le conteneur, pas le
    contenu : ce qui remonte du disque a pu être écrit par une version
    antérieure, et lever ici empêcherait l'intégration de se charger."""

    def test_a_round_trip_keeps_everything(self):
        original = dataclasses.replace(
            models.new_remediation("nas_media", "/media/frigate", "stop_only"),
            state="repairing",
            step="reloading",
            started_at="2026-09-20T18:00:00+00:00",
            addons=(models.RemediationAddon("frigate", "Frigate", "held"),),
            files_total=10,
            files_done=4,
            last_error="boum",
            history=(
                models.RemediationTransition(
                    at="2026-09-20T18:00:00+00:00", from_="degraded", to="repairing"
                ),
            ),
        )
        assert models.from_wire(models.to_wire(original)) == original

    def test_the_history_survives_a_restart(self):
        """Ce qui s'est passé cette nuit est précisément ce qu'on relit le
        matin. Le perdre au redémarrage viderait le journal de son intérêt."""
        original = dataclasses.replace(
            models.new_remediation("m", "/media/m"),
            history=(
                models.RemediationTransition(at="2026-09-20T18:00:00+00:00", from_="ok",
                                             to="degraded", error="NAS absent"),
            ),
        )
        assert models.from_wire(models.to_wire(original)).history[0].error == "NAS absent"

    def test_an_unknown_state_falls_back_instead_of_propagating(self):
        """Relu sans filtre, il se propagerait jusqu'à `needs_remediation`, qui
        répondrait non, et l'add-on repartirait au milieu d'une remédiation."""
        rebuilt = models.from_wire({"mount": "m", "path": "/media/m", "state": "bizarre"})
        assert rebuilt.state == "ok"

    def test_the_step_index_is_recomputed_not_reread(self):
        """Un couple (step, step_index) incohérent relu tel quel ferait pointer
        le stepper sur une étape qui n'est pas celle qui tourne."""
        rebuilt = models.from_wire(
            {"mount": "m", "path": "/media/m", "step": "restoring", "step_index": 99}
        )
        assert rebuilt.step_index == 4


class TestStepIndexCannotLieEither:
    """Même verrou que `step_count`, et pour la même raison : ce sont des
    dérivations, pas des données."""

    def test_a_replace_on_the_step_moves_the_index(self):
        """Sans ce recalage, le stepper resterait allumé sur l'étape
        précédente pendant toute la suivante."""
        base = models.new_remediation("m", "/media/m")
        assert dataclasses.replace(base, step="reloading").step_index == 3

    def test_a_replace_on_the_mode_renumbers_the_step(self):
        base = dataclasses.replace(
            models.new_remediation("m", "/media/m"), step="starting"
        )
        assert base.step_index == 5
        assert dataclasses.replace(base, mode="stop_only").step_index == 3

    def test_a_garbled_payload_is_refused_not_repaired(self):
        for payload in (None, [], "texte", {}, {"mount": "m"}, {"path": "/media/m"}):
            assert models.from_wire(payload) is None

    def test_junk_entries_are_dropped_not_fatal(self):
        rebuilt = models.from_wire({
            "mount": "m", "path": "/media/m",
            "addons": [{"slug": "ok"}, {"name": "sans slug"}, "texte"],
            "history": [{"at": "2026-01-01T00:00:00+00:00"}, {"error": "sans date"}],
        })
        assert [a.slug for a in rebuilt.addons] == ["ok"]
        assert len(rebuilt.history) == 1

    def test_the_history_is_capped_on_the_way_in_too(self):
        """Un état écrit par une version dont le plafond était plus haut ferait
        sinon grossir chaque écriture d'attribut, donc chaque ligne de
        recorder."""
        entries = [
            {"at": f"2026-01-01T00:00:{i:02d}+00:00", "from": "ok", "to": "degraded"}
            for i in range(30)
        ]
        rebuilt = models.from_wire({"mount": "m", "path": "/media/m", "history": entries})
        assert len(rebuilt.history) == HISTORY_LENGTH
