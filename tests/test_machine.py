"""La machine à états, et les deux règles sur les add-ons partagés.

C'est le module qui décide d'arrêter un add-on et de déplacer des fichiers. Un
faux positif arrête Frigate sans raison ; un faux négatif laisse des
enregistrements orphelins sur la carte SD. Aucun des deux ne se voit sur un
tableau de bord, et c'est pour ça que tout y est pur et testé ici.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.addon_mount_guard import machine
from custom_components.addon_mount_guard.models import (
    HISTORY_LENGTH,
    RemediationAddon,
    new_remediation,
)
from custom_components.addon_mount_guard.mount_table import build_mount_table

T0 = datetime(2026, 9, 20, 18, 0, 0, tzinfo=UTC)


def rem(**changes):
    return dataclasses.replace(new_remediation("nas_media", "/media/nas_media"), **changes)


# --- observation --------------------------------------------------------


class TestObserve:
    def test_a_lost_mount_degrades(self):
        after = machine.observe(rem(), mounted=False, reachable=False, now=T0)
        assert after.state == "degraded"
        assert after.last_incident_at == T0.isoformat()

    def test_a_degraded_mount_whose_nas_answers_becomes_pending(self):
        after = machine.observe(rem(state="degraded"), mounted=False, reachable=True, now=T0)
        assert after.state == "pending"

    def test_a_degraded_mount_whose_nas_is_silent_stays_degraded(self):
        """Le repli assumé : l'add-on écrit en local et il n'y a rien à faire."""
        before = rem(state="degraded")
        assert machine.observe(before, mounted=False, reachable=False, now=T0) is before

    def test_a_pending_mount_whose_nas_leaves_again_falls_back(self):
        """Et ce retour libère du même coup les add-ons que ce `pending`
        retenait à l'arrêt sur leurs autres montages."""
        after = machine.observe(rem(state="pending"), mounted=False, reachable=False, now=T0)
        assert after.state == "degraded"

    def test_a_repairing_mount_is_never_observed(self):
        """La séquence pilote. Un relevé arrivé au milieu de l'étape 3 verrait
        un montage absent qu'elle vient elle-même de recharger."""
        before = rem(state="repairing", step="reloading")
        assert machine.observe(before, mounted=False, reachable=True, now=T0) is before
        assert machine.observe(before, mounted=True, reachable=True, now=T0) is before

    def test_a_healthy_mount_produces_no_copy(self):
        """Une copie à chaque cycle ferait réécrire l'attribut d'entité toutes
        les soixante secondes, donc une ligne de recorder par minute et par
        montage, pour rien."""
        before = rem()
        assert machine.observe(before, mounted=True, reachable=True, now=T0) is before


class TestRetryBackoff:
    def test_before_the_deadline_it_stays_degraded(self):
        before = rem(state="degraded", next_retry_at=(T0 + timedelta(seconds=120)).isoformat())
        assert machine.observe(before, mounted=False, reachable=True, now=T0).state == "degraded"

    def test_after_the_deadline_it_becomes_pending(self):
        before = rem(state="degraded", next_retry_at=(T0 - timedelta(seconds=1)).isoformat())
        after = machine.observe(before, mounted=False, reachable=True, now=T0)
        assert after.state == "pending"

    def test_the_deadline_is_cleared_on_the_way_out(self):
        """Laissé en place, il ferait afficher un compte à rebours périmé sur la
        ligne d'un montage en cours de réparation."""
        before = rem(state="degraded", next_retry_at=(T0 - timedelta(seconds=1)).isoformat())
        assert machine.observe(before, mounted=False, reachable=True, now=T0).next_retry_at is None


class TestSpontaneousRemount:
    """Le seul cas que l'intégration ne sait pas rattraper."""

    @pytest.mark.parametrize("state", ["degraded", "pending"])
    def test_it_returns_to_ok_but_says_what_was_lost(self, state):
        after = machine.observe(rem(state=state), mounted=True, reachable=True, now=T0)
        assert after.state == "ok"
        assert after.last_error == machine.ERROR_MASKED_LOCAL_FILES

    def test_the_journal_keeps_the_trace(self):
        """C'est la seule façon pour l'utilisateur de comprendre, plus tard,
        pourquoi il manque une heure d'enregistrements."""
        after = machine.observe(rem(state="degraded"), mounted=True, reachable=True, now=T0)
        assert after.history[0].error == machine.ERROR_MASKED_LOCAL_FILES


# --- journal ------------------------------------------------------------


class TestTransitionJournal:
    def test_the_most_recent_entry_comes_first(self):
        after = machine.observe(rem(), mounted=False, reachable=False, now=T0)
        after = machine.observe(after, mounted=False, reachable=True, now=T0)
        assert (after.history[0].from_, after.history[0].to) == ("degraded", "pending")

    def test_it_is_capped(self):
        current = rem()
        for i in range(HISTORY_LENGTH * 2):
            current = machine.transition(
                current, to="degraded" if i % 2 else "ok", now=T0
            )
        assert len(current.history) == HISTORY_LENGTH

    def test_the_incident_timestamp_marks_the_start_not_the_last_jolt(self):
        """Ce que lit le capteur « dernier incident » est le début de la panne.
        Le réécrire à chaque transition ferait remonter l'heure à chaque échec
        de réparation, et l'utilisateur croirait la panne plus récente."""
        degraded = machine.observe(rem(), mounted=False, reachable=False, now=T0)
        later = machine.transition(degraded, to="pending", now=T0 + timedelta(minutes=30))
        assert later.last_incident_at == T0.isoformat()

    def test_an_error_does_not_survive_a_return_to_ok(self):
        """Sinon la carte afficherait une erreur sur un montage sain."""
        failed = machine.fail(rem(state="repairing"), now=T0, error="boum", retry_interval=120)
        assert failed.last_error == "boum"
        assert machine.succeed(failed, now=T0).last_error is None


class TestEnterStep:
    def test_it_does_not_journal(self):
        """L'invariant qui garde le journal lisible : une séquence réussie
        consommerait sinon cinq des dix entrées, et il ne resterait rien de
        l'incident précédent — or c'est celui qu'on relit."""
        repairing = machine.start_repair(rem(state="pending"), now=T0)
        before = len(repairing.history)
        current = repairing
        for step in ("stopping", "stashing", "reloading", "restoring", "starting"):
            current = machine.enter_step(current, step, now=T0)
        assert len(current.history) == before

    def test_it_numbers_the_step(self):
        current = machine.enter_step(rem(state="repairing"), "restoring", now=T0)
        assert (current.step, current.step_index, current.step_count) == ("restoring", 4, 5)

    def test_stop_only_numbers_only_its_own_steps(self):
        current = machine.enter_step(rem(state="repairing", mode="stop_only"), "starting", now=T0)
        assert (current.step_index, current.step_count) == (3, 3)


class TestStartAndFinish:
    def test_starting_resets_the_progress_counters(self):
        """Une remédiation qui a échoué en `restoring` garde sinon ses
        compteurs, et la carte affiche « 613 / 1284 » pendant l'étape 1 de la
        tentative suivante."""
        stale = rem(state="pending", files_total=1284, files_done=613, current_file="a.mp4")
        after = machine.start_repair(stale, now=T0)
        assert (after.files_total, after.files_done, after.current_file) == (0, 0, None)
        assert after.started_at == T0.isoformat()

    def test_failing_goes_back_to_degraded_not_pending(self):
        """`pending` retiendrait les add-ons des autres montages à l'arrêt
        pendant toute l'attente, et un réessai immédiat sur un NAS qui répond au
        TCP sans avoir fini d'exporter arrêterait tout en boucle."""
        after = machine.fail(rem(state="repairing"), now=T0, error="boum", retry_interval=120)
        assert after.state == "degraded"
        assert after.next_retry_at == (T0 + timedelta(seconds=120)).isoformat()


class TestConsecutiveFailures:
    def test_it_counts_the_run_of_failures(self):
        current = rem()
        for _ in range(3):
            current = machine.fail(
                dataclasses.replace(current, state="repairing"),
                now=T0,
                error="boum",
                retry_interval=120,
            )
        assert machine.consecutive_failures(current) == 3

    def test_a_success_resets_it(self):
        """Sinon la réparation Home Assistant s'ouvrirait sur un montage qui
        vient de se réparer tout seul."""
        failed = machine.fail(rem(state="repairing"), now=T0, error="boum", retry_interval=120)
        healed = machine.succeed(dataclasses.replace(failed, state="repairing"), now=T0)
        assert machine.consecutive_failures(healed) == 0

    def test_a_degradation_without_error_is_not_a_failure(self):
        """Une panne de NAS n'est pas un échec de réparation : la compter
        ouvrirait une réparation Home Assistant au bout de trois coupures
        réseau, sur lesquelles l'utilisateur n'a rien à faire."""
        degraded = machine.observe(rem(), mounted=False, reachable=False, now=T0)
        assert machine.consecutive_failures(degraded) == 0


# --- add-ons partagés ---------------------------------------------------

OPTIONS = {
    "nas_media": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "media"},
    "nas_config": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "share"},
}
TABLE = build_mount_table(
    OPTIONS, [{"slug": "frigate", "mounts": ["nas_media", "nas_config"]}]
)


def states(media: str, config: str) -> dict:
    return {
        "nas_media": rem(state=media),
        "nas_config": dataclasses.replace(
            new_remediation("nas_config", "/share/nas_config"), state=config
        ),
    }


class TestPlanRestart:
    def test_a_degraded_sibling_does_not_hold_the_addon(self):
        """LA règle. Le NAS du second montage est absent : Frigate doit repartir
        en local, c'est tout l'objet de `local_fallback`. Le retenir le
        laisserait arrêté aussi longtemps que ce NAS resterait éteint."""
        plan = machine.plan_restart(
            "nas_media", TABLE, states("repairing", "degraded"), {"frigate": True}
        )
        assert plan.start == ("frigate",)
        assert plan.held == ()

    @pytest.mark.parametrize("sibling", ["pending", "repairing"])
    def test_a_sibling_that_needs_work_holds_it(self, sibling):
        """Il faudrait le rearrêter dans la minute, et entre les deux il
        écrirait en local exactement ce qu'on vient de rapatrier."""
        plan = machine.plan_restart(
            "nas_media", TABLE, states("repairing", sibling), {"frigate": True}
        )
        assert plan.held == ("frigate",)
        assert plan.start == ()

    def test_a_healthy_sibling_does_not_hold_it(self):
        plan = machine.plan_restart(
            "nas_media", TABLE, states("repairing", "ok"), {"frigate": True}
        )
        assert plan.start == ("frigate",)

    def test_an_addon_we_never_stopped_is_left_alone(self):
        """L'utilisateur l'avait arrêté lui-même. Le démarrer en sortie de
        réparation serait une initiative que rien n'a demandée."""
        plan = machine.plan_restart(
            "nas_media", TABLE, states("repairing", "ok"), {"frigate": False}
        )
        assert plan.untouched == ("frigate",)
        assert plan.start == ()

    def test_the_mount_being_repaired_never_holds_itself(self):
        """Il est `repairing` au moment où l'on pose la question : s'inclure
        retiendrait l'add-on à chaque fin de séquence, donc toujours."""
        table = build_mount_table(
            {"nas_media": OPTIONS["nas_media"]}, [{"slug": "frigate", "mounts": ["nas_media"]}]
        )
        plan = machine.plan_restart(
            "nas_media", table, {"nas_media": rem(state="repairing")}, {"frigate": True}
        )
        assert plan.start == ("frigate",)


class TestTheBatchingFallsOutOfTheRule:
    """Deux montages du même add-on qui reviennent ensemble : UN arrêt, UNE
    relance. Il n'y a pas de mécanisme de lot, et il n'y en a pas besoin."""

    def test_the_first_sequence_holds_and_the_second_releases(self):
        stopped = {"frigate": True}

        # Réparation de nas_media pendant que nas_config attend la sienne.
        first = machine.plan_restart("nas_media", TABLE, states("repairing", "pending"), stopped)
        assert first.held == ("frigate",)

        # Puis réparation de nas_config, nas_media étant rentré dans l'ordre.
        second = machine.plan_restart("nas_config", TABLE, states("ok", "repairing"), stopped)
        assert second.start == ("frigate",)


class TestDiskGuard:
    def test_it_stops_the_running_addons_below_the_threshold(self):
        current = rem(state="degraded", addons=(RemediationAddon("frigate", "Frigate", "started"),))
        assert machine.disk_guard(current, free_ratio=0.04, threshold=0.10) == ("frigate",)

    def test_it_says_nothing_above_the_threshold(self):
        current = rem(state="degraded", addons=(RemediationAddon("frigate", "Frigate", "started"),))
        assert machine.disk_guard(current, free_ratio=0.50, threshold=0.10) == ()

    def test_a_threshold_of_zero_disables_it(self):
        """La seule façon de refuser ce comportement sans désinstaller
        l'intégration."""
        current = rem(state="degraded", addons=(RemediationAddon("frigate", "Frigate", "started"),))
        assert machine.disk_guard(current, free_ratio=0.0, threshold=0.0) == ()

    @pytest.mark.parametrize("state", ["ok", "pending", "repairing"])
    def test_it_only_applies_while_the_addon_writes_locally(self, state):
        current = dataclasses.replace(
            rem(addons=(RemediationAddon("frigate", "Frigate", "started"),)), state=state
        )
        assert machine.disk_guard(current, free_ratio=0.01, threshold=0.10) == ()

    def test_an_already_stopped_addon_is_not_stopped_again(self):
        """Sinon un ordre d'arrêt sans effet partirait à chaque cycle de
        polling, soit une ligne de journal par minute jusqu'au retour du NAS."""
        current = rem(state="degraded", addons=(RemediationAddon("frigate", "Frigate", "stopped"),))
        assert machine.disk_guard(current, free_ratio=0.01, threshold=0.10) == ()


class TestStashedFilesForceARemediation:
    """`<chemin>_local` est l'état persistant qui survit à tout, redémarrage de
    Home Assistant compris. C'est lui qui fait reprendre une séquence
    interrompue, sans qu'on ait à savoir où elle s'était arrêtée."""

    def test_an_interrupted_sequence_resumes_even_if_the_mount_is_back(self):
        """Le cas de la reprise : Home Assistant redémarre, le Supervisor
        remonte le partage, et les fichiers attendent dans le répertoire
        frère — que le bind mount ne recouvre pas."""
        after = machine.observe(
            rem(state="degraded"), mounted=True, reachable=True, now=T0, stashed=True
        )
        assert after.state == "pending"
        assert after.last_error != machine.ERROR_MASKED_LOCAL_FILES

    def test_it_resumes_even_if_the_mount_is_still_absent(self):
        after = machine.observe(
            rem(state="degraded"), mounted=False, reachable=False, now=T0, stashed=True
        )
        assert after.state == "pending"

    def test_leftovers_on_a_healthy_mount_are_picked_up_too(self):
        """Reste d'un échec ancien : personne d'autre ne les rapatriera."""
        after = machine.observe(rem(), mounted=True, reachable=True, now=T0, stashed=True)
        assert after.state == "pending"

    def test_the_retry_backoff_still_applies(self):
        """Sinon une réparation qui échoue en boucle relancerait la séquence à
        chaque cycle de polling, soit toutes les soixante secondes."""
        before = rem(state="degraded", next_retry_at=(T0 + timedelta(seconds=120)).isoformat())
        assert machine.observe(
            before, mounted=False, reachable=True, now=T0, stashed=True
        ).state == "degraded"

    def test_without_a_stash_a_returned_mount_is_not_a_remediation(self):
        """Même en `pending`. Une séquence qui démarrerait maintenant mettrait
        de côté le contenu DU NAS, puisque c'est lui qu'on voit désormais sous
        le point de montage — le partage serait vidé, l'opération réussirait, et
        rien ne le signalerait."""
        after = machine.observe(rem(state="pending"), mounted=True, reachable=True, now=T0)
        assert after.state == "ok"
        assert after.last_error == machine.ERROR_MASKED_LOCAL_FILES
