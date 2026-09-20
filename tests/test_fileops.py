"""Les opérations sur les fichiers, sur un vrai système de fichiers temporaire.

C'est le module qui peut détruire des données. Les tests portent donc moins sur
le chemin nominal que sur les trois façons d'en perdre : écraser une version
plus récente, supprimer la source avant que la copie soit sûre, et interrompre
une copie en cours.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from custom_components.addon_mount_guard import fileops


def write(path: Path, content: str, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


@pytest.fixture
def mount(tmp_path: Path) -> Path:
    target = tmp_path / "media" / "frigate"
    target.mkdir(parents=True)
    return target


class TestStashDir:
    def test_it_is_a_sibling_not_a_child(self, mount):
        """Le choix qui rend la reprise possible : le bind mount recouvre le
        point de montage, pas son voisin. Un `_local` placé dessous
        disparaîtrait au rechargement de l'étape 3, avec tout ce qu'on venait
        d'y mettre."""
        stashed = fileops.stash_dir(mount)
        assert stashed.parent == mount.parent
        assert stashed.name == "frigate_local"


class TestIsMounted:
    def test_it_reads_the_second_field(self, tmp_path):
        proc = write(tmp_path / "mounts", "//10.0.0.12/media /media/frigate cifs rw 0 0\n")
        assert fileops.is_mounted(Path("/media/frigate"), proc) is True
        assert fileops.is_mounted(Path("/media/autre"), proc) is False

    def test_octal_escapes_are_decoded(self):
        """Un partage nommé « mes films » ne serait jamais reconnu comme monté,
        et l'intégration le réparerait en boucle."""
        assert fileops._unescape("/media/mes\\040films") == "/media/mes films"

    def test_an_unreadable_proc_assumes_mounted(self, tmp_path):
        """Ni HA OS ni Supervised. Répondre « non monté » déclencherait une
        réparation sur une installation où il n'y a rien à réparer."""
        assert fileops.is_mounted(Path("/media/x"), tmp_path / "absent") is True


class TestFreeRatio:
    def test_it_is_between_zero_and_one(self, tmp_path):
        assert 0.0 <= fileops.free_ratio(tmp_path) <= 1.0

    def test_an_error_reads_as_plenty_of_room(self, tmp_path):
        """Renvoyer 0 ferait arrêter les add-ons sur une simple erreur de
        lecture, soit l'inverse de ce qu'on attend d'un garde-fou."""
        assert fileops.free_ratio(tmp_path / "nexiste" / "pas") == 1.0


class TestMeasure:
    def test_it_counts_files_and_bytes(self, mount):
        write(mount / "a.txt", "12345")
        write(mount / "sous" / "b.txt", "123")
        assert fileops.measure(mount) == (2, 8)

    def test_an_empty_tree_measures_zero(self, mount):
        assert fileops.measure(mount) == (0, 0)


class TestStash:
    def test_it_moves_the_content_not_the_directory(self, mount):
        """Le point de montage est un bind mount : le renommer lève EBUSY.
        C'est le piège qui fait écrire cette étape à l'envers la première
        fois."""
        write(mount / "clips" / "a.mp4", "aaa")
        result = fileops.stash(mount)
        assert mount.is_dir()
        assert list(mount.iterdir()) == []
        assert (fileops.stash_dir(mount) / "clips" / "a.mp4").read_text() == "aaa"
        assert result.moved == 1

    def test_it_is_idempotent_and_merges(self, mount):
        """Relancée après une coupure, elle reprend ce qui reste — c'est ce qui
        permet à la reprise au démarrage de ne pas savoir où la précédente
        s'était arrêtée. Sans fusion, le second passage renommerait tout un
        arbre parce que son répertoire racine existe déjà."""
        write(mount / "clips" / "a.mp4", "aaa")
        fileops.stash(mount)
        write(mount / "clips" / "b.mp4", "bbb")
        fileops.stash(mount)
        stashed = fileops.stash_dir(mount)
        assert sorted(p.name for p in (stashed / "clips").iterdir()) == ["a.mp4", "b.mp4"]

    def test_a_file_collision_destroys_nothing(self, mount):
        write(mount / "clips" / "a.mp4", "nouveau")
        write(fileops.stash_dir(mount) / "clips" / "a.mp4", "ancien")
        result = fileops.stash(mount)
        stashed = fileops.stash_dir(mount) / "clips"
        assert result.conflicts == 1
        assert {p.read_text() for p in stashed.iterdir()} == {"ancien", "nouveau"}


class TestRollback:
    def test_it_puts_everything_back_and_removes_the_stash(self, mount):
        """Ne rien faire laisserait l'add-on redémarrer sur un répertoire vide,
        ce qui ressemble à une perte de données même quand tout est encore là,
        à côté."""
        write(mount / "clips" / "a.mp4", "aaa")
        fileops.stash(mount)
        fileops.rollback(mount)
        assert (mount / "clips" / "a.mp4").read_text() == "aaa"
        assert not fileops.stash_dir(mount).exists()

    def test_without_a_stash_it_does_nothing(self, mount):
        assert fileops.rollback(mount).moved == 0


class TestRestore:
    def test_it_copies_and_removes_the_stash(self, mount):
        write(mount / "a.txt", "aaa")
        fileops.stash(mount)
        result = fileops.restore(mount)
        assert (mount / "a.txt").read_text() == "aaa"
        assert not fileops.stash_dir(mount).exists()
        assert (result.copied, result.skipped, result.complete) == (1, 0, True)

    def test_a_newer_file_on_the_nas_is_never_overwritten(self, mount):
        """Pendant la panne, un autre appareil a pu écrire sur le partage. Sa
        version est la bonne ; la nôtre a été écrite en aveugle par un add-on
        qui croyait parler au NAS."""
        stashed = fileops.stash_dir(mount)
        write(stashed / "a.txt", "local ancien", mtime=time.time() - 100)
        write(mount / "a.txt", "nas récent", mtime=time.time())
        result = fileops.restore(mount)
        assert (mount / "a.txt").read_text() == "nas récent"
        assert (result.copied, result.skipped) == (0, 1)

    def test_an_older_file_on_the_nas_is_replaced(self, mount):
        stashed = fileops.stash_dir(mount)
        write(stashed / "a.txt", "local récent", mtime=time.time())
        write(mount / "a.txt", "nas ancien", mtime=time.time() - 100)
        fileops.restore(mount)
        assert (mount / "a.txt").read_text() == "local récent"

    def test_metadata_is_preserved(self, mount):
        """Une date perdue ferait réécrire le fichier au rapatriement suivant,
        et surtout Frigate range ses enregistrements par date."""
        stashed = fileops.stash_dir(mount)
        when = time.time() - 4242
        write(stashed / "a.txt", "aaa", mtime=when)
        fileops.restore(mount)
        assert (mount / "a.txt").stat().st_mtime == pytest.approx(when, abs=1)

    def test_progress_is_reported_per_file(self, mount):
        stashed = fileops.stash_dir(mount)
        write(stashed / "a.txt", "12345")
        write(stashed / "b.txt", "123")
        seen: list[tuple[int, int, str]] = []
        fileops.restore(
            mount, concurrency=1, on_progress=lambda f, b, name: seen.append((f, b, name))
        )
        assert seen == [(1, 5, "a.txt"), (2, 8, "b.txt")]

    def test_the_order_is_stable_when_sequential(self, mount):
        """`concurrency=1` explicitement : au-delà, l'ordre d'achèvement n'est
        plus celui du parcours, et c'est le prix assumé de la parallélisation —
        voir TestConcurrency. Le parcours lui-même (`iter_files`) reste trié."""
        stashed = fileops.stash_dir(mount)
        for name in ("c.txt", "a.txt", "b.txt"):
            write(stashed / name, "x")
        seen: list[str] = []
        fileops.restore(mount, concurrency=1, on_progress=lambda f, b, name: seen.append(name))
        assert seen == ["a.txt", "b.txt", "c.txt"]


class TestOverwritePolicy:
    """Réglée par montage : un partage d'enregistrements de caméra, dont
    l'add-on est le seul écrivain, et un partage de documents que plusieurs
    appareils modifient n'ont pas la même réponse. Un réglage unique obligerait
    à choisir la prudence pour tout le monde, donc à laisser Frigate perdre les
    siens."""

    @pytest.fixture
    def conflit(self, mount):
        """Le local est ANCIEN, le NAS est récent : le cas où les trois
        politiques divergent."""
        stashed = fileops.stash_dir(mount)
        write(stashed / "a.txt", "local", mtime=time.time() - 100)
        write(mount / "a.txt", "nas", mtime=time.time())
        return mount

    def test_keep_newest_is_the_default(self, conflit):
        fileops.restore(conflit)
        assert (conflit / "a.txt").read_text() == "nas"

    def test_always_lets_the_local_copy_win(self, conflit):
        """Pour un montage dont l'add-on est le seul écrivain : la version
        locale est par construction la plus à jour, même si l'horloge dit
        autre chose."""
        fileops.restore(conflit, overwrite="always")
        assert (conflit / "a.txt").read_text() == "local"

    def test_never_leaves_the_nas_untouched(self, conflit):
        stashed = fileops.stash_dir(conflit)
        write(stashed / "a.txt", "local", mtime=time.time())
        write(conflit / "a.txt", "nas", mtime=time.time() - 100)
        fileops.restore(conflit, overwrite="never")
        assert (conflit / "a.txt").read_text() == "nas"

    @pytest.mark.parametrize("policy", ["keep_newest", "always", "never"])
    def test_no_policy_ever_discards_a_file_absent_from_the_nas(self, policy, mount):
        """Aucune des trois ne dit « jeter ». `never` protège ce qui EXISTE
        côté NAS, il ne refuse pas les nouveaux venus — le confondre viderait
        le rapatriement de son sens."""
        write(fileops.stash_dir(mount) / "neuf.txt", "neuf")
        fileops.restore(mount, overwrite=policy)
        assert (mount / "neuf.txt").read_text() == "neuf"

    def test_an_unreadable_policy_falls_back_to_the_safe_one(self, conflit):
        """Configuration écrite à la main, ou option retirée d'une version
        future : un réglage illisible ne doit pas se traduire par un
        écrasement."""
        fileops.restore(conflit, overwrite="n_importe_quoi")
        assert (conflit / "a.txt").read_text() == "nas"

    def test_a_skipped_file_still_counts_in_the_progress(self, conflit):
        """Sinon la barre s'arrête avant la fin sur un montage où la plupart
        des fichiers sont déjà à jour, et la remédiation semble bloquée."""
        result = fileops.restore(conflit)
        assert (result.copied, result.skipped) == (0, 1)
        assert result.complete is True


class TestConcurrency:
    """Le seul levier qui change l'ordre de grandeur.

    Le coût d'un rapatriement est la LATENCE, pas le débit : mesuré sur une
    installation réelle, environ dix fichiers par seconde en séquentiel, soit
    plus de deux heures pour 83 000 vignettes. Ces tests vérifient que le
    parallélisme ne coûte aucune des garanties de sûreté.
    """

    @pytest.fixture
    def many(self, mount):
        stashed = fileops.stash_dir(mount)
        for index in range(60):
            write(stashed / f"dossier{index % 5}" / f"f{index:03d}.txt", "x" * (index + 1))
        return mount

    def test_everything_arrives(self, many):
        result = fileops.restore(many, concurrency=8)
        assert result.complete is True
        assert result.copied == 60
        assert sum(1 for _ in fileops.iter_files(many)) == 60
        assert not fileops.stash_dir(many).exists()

    def test_the_counters_are_exact(self, many):
        """Incréments sous verrou. Sans lui, deux threads qui lisent-modifient
        -écrivent le même compteur en perdent : la barre n'atteindrait jamais
        son total, et `complete` porterait sur un décompte faux."""
        expected_bytes = sum(index + 1 for index in range(60))
        result = fileops.restore(many, concurrency=8)
        assert (result.copied + result.skipped, result.bytes_done) == (60, expected_bytes)

    def test_the_progress_counters_never_go_backwards(self, many):
        """L'ordre des fichiers varie, mais le compteur qui pilote la barre doit
        rester monotone : une barre qui recule est le symptôme le plus visible
        d'un état partagé mal protégé."""
        seen: list[int] = []
        fileops.restore(many, concurrency=8, on_progress=lambda f, b, name: seen.append(f))
        assert seen == sorted(seen)
        assert seen[-1] == 60

    def test_each_directory_is_created_once(self, many, monkeypatch):
        """L'économie la plus rentable de la fonction : un `mkdir` par fichier
        est un aller-retour réseau par fichier. Frigate range ses
        enregistrements par caméra et par heure, donc quelques centaines de
        répertoires pour des dizaines de milliers de fichiers."""
        calls: list[Path] = []
        real = Path.mkdir

        def spy(self, *args, **kwargs):
            calls.append(self)
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", spy)
        fileops.restore(many, concurrency=8)
        assert len(calls) == 5, calls

    def test_cancellation_still_happens_between_files(self, many):
        """Aucune copie n'est interrompue en cours : l'annulation est consultée
        avant chaque soumission. Un fichier tronqué sur le NAS serait
        indiscernable d'un fichier valide."""
        result = fileops.restore(many, concurrency=8, should_cancel=lambda: True)
        assert result.cancelled is True
        assert result.complete is False
        assert fileops.stash_dir(many).exists()

    def test_a_cancelled_run_resumes_and_finishes(self, many):
        calls = {"n": 0}

        def cancel_after_a_while() -> bool:
            calls["n"] += 1
            return calls["n"] > 10

        fileops.restore(many, concurrency=4, should_cancel=cancel_after_a_while)
        assert fileops.restore(many, concurrency=4).complete is True
        assert sum(1 for _ in fileops.iter_files(many)) == 60

    def test_one_failure_does_not_stop_the_others(self, many):
        bad = next(fileops.iter_files(fileops.stash_dir(many)))
        bad.chmod(0o000)
        try:
            result = fileops.restore(many, concurrency=8)
        finally:
            bad.chmod(0o644)
        assert result.complete is False
        assert len(result.errors) == 1
        assert result.copied == 59
        assert fileops.stash_dir(many).exists()

    def test_sequential_and_concurrent_agree(self, mount):
        """Le parallélisme est une optimisation, pas un comportement : à
        contenu égal, les deux chemins doivent rendre le même résultat."""
        stashed = fileops.stash_dir(mount)
        for index in range(20):
            write(stashed / f"f{index}.txt", "x" * index)
        sequential = fileops.restore(mount, concurrency=1)

        other = mount.parent / "autre"
        other.mkdir()
        stashed2 = fileops.stash_dir(other)
        for index in range(20):
            write(stashed2 / f"f{index}.txt", "x" * index)
        concurrent = fileops.restore(other, concurrency=8)

        assert (sequential.copied, sequential.bytes_done) == (
            concurrent.copied,
            concurrent.bytes_done,
        )


class TestMetadata:
    def test_the_modification_date_is_preserved(self, mount):
        """Ce dont tout dépend : la politique `keep_newest` la compare, et
        Frigate range ses enregistrements par date. Une copie qui ne la
        préserverait pas daterait tous les fichiers de l'instant du
        rapatriement, et le rapatriement suivant les croirait tous récents."""
        stashed = fileops.stash_dir(mount)
        when = time.time() - 4242
        write(stashed / "a.txt", "aaa", mtime=when)
        fileops.restore(mount)
        assert (mount / "a.txt").stat().st_mtime == pytest.approx(when, abs=1)

    def test_the_content_is_intact(self, mount):
        stashed = fileops.stash_dir(mount)
        (stashed).mkdir(parents=True, exist_ok=True)
        (stashed / "a.bin").write_bytes(bytes(range(256)) * 100)
        fileops.restore(mount)
        assert (mount / "a.bin").read_bytes() == bytes(range(256)) * 100


class TestRestoreCancellation:
    def test_it_stops_between_two_files_and_keeps_the_stash(self, mount):
        """`cancel` est un service que l'utilisateur déclenche : il ne doit pas
        pouvoir corrompre quoi que ce soit. Interrompre un copy2 laisserait un
        fichier tronqué sur le NAS, indiscernable d'un fichier valide."""
        stashed = fileops.stash_dir(mount)
        for name in ("a.txt", "b.txt", "c.txt"):
            write(stashed / name, "x")
        calls = {"n": 0}

        def should_cancel() -> bool:
            calls["n"] += 1
            return calls["n"] > 2

        result = fileops.restore(mount, should_cancel=should_cancel)
        assert result.cancelled is True
        assert result.complete is False
        # La source est intacte : rien n'est perdu, la reprise finira le travail.
        assert fileops.stash_dir(mount).exists()
        assert result.copied == 2

    def test_a_cancelled_restore_resumes_without_recopying(self, mount):
        stashed = fileops.stash_dir(mount)
        for name in ("a.txt", "b.txt"):
            write(stashed / name, "x")
        fileops.restore(mount, should_cancel=lambda: True)
        result = fileops.restore(mount)
        assert result.complete is True
        assert sorted(p.name for p in mount.iterdir()) == ["a.txt", "b.txt"]


class TestRestoreErrors:
    def test_one_unreadable_file_does_not_stop_the_others(self, mount):
        """Un fichier illisible ne doit pas empêcher les mille autres de
        rentrer."""
        stashed = fileops.stash_dir(mount)
        write(stashed / "a.txt", "aaa")
        bad = write(stashed / "b.txt", "bbb")
        bad.chmod(0o000)
        try:
            result = fileops.restore(mount)
        finally:
            bad.chmod(0o644)
        assert (mount / "a.txt").read_text() == "aaa"
        assert result.errors

    def test_an_incomplete_restore_keeps_the_stash(self, mount):
        """La source n'est supprimée qu'après un parcours complet et sans
        erreur : une source supprimée au fil de l'eau laisse, après une
        coupure, la moitié des fichiers nulle part."""
        stashed = fileops.stash_dir(mount)
        bad = write(stashed / "b.txt", "bbb")
        bad.chmod(0o000)
        try:
            result = fileops.restore(mount)
        finally:
            bad.chmod(0o644)
        assert result.complete is False
        assert stashed.exists()

    def test_without_a_stash_it_is_a_noop(self, mount):
        assert fileops.restore(mount).complete is True
