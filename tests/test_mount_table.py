"""Les deux tables qui relient add-ons et montages.

La table inversée (`mount -> [slugs]`) saute aux yeux ; c'est la table directe
(`slug -> [mounts]`) qu'on oublie, et son absence ne se voit qu'au moment où un
add-on à deux montages redémarre trop tôt. Les deux sont donc construites
ensemble et testées ensemble.
"""
from __future__ import annotations

from custom_components.addon_mount_guard.mount_table import build_mount_table, mount_path

OPTIONS = {
    "nas_media": {"host": "10.0.0.12", "mode": "local_fallback", "usage": "media"},
    "nas_config": {"host": "10.0.0.12", "mode": "stop_only", "usage": "share"},
}

FRIGATE = {"slug": "ccab4aaf_frigate", "mounts": ["nas_media", "nas_config"]}
MOTIONEYE = {"slug": "core_motioneye", "mounts": ["nas_media"]}


class TestMountPath:
    def test_it_follows_the_usage(self):
        assert mount_path("nas_media", "media") == "/media/nas_media"
        assert mount_path("docs", "share") == "/share/docs"


class TestBothDirections:
    def test_the_inverted_table_lists_every_addon_of_a_mount(self):
        table = build_mount_table(OPTIONS, [FRIGATE, MOTIONEYE])
        assert table.slugs_for("nas_media") == ("ccab4aaf_frigate", "core_motioneye")
        assert table.slugs_for("nas_config") == ("ccab4aaf_frigate",)

    def test_the_direct_table_lists_every_mount_of_an_addon(self):
        """Celle qu'on oublie. Sans elle, la réparation de nas_media relancerait
        Frigate alors que nas_config attend la sienne."""
        table = build_mount_table(OPTIONS, [FRIGATE, MOTIONEYE])
        assert table.mounts_for("ccab4aaf_frigate") == ("nas_config", "nas_media")
        assert table.mounts_for("core_motioneye") == ("nas_media",)

    def test_other_mounts_excludes_the_one_being_repaired(self):
        """La question réellement posée avant chaque relance."""
        table = build_mount_table(OPTIONS, [FRIGATE])
        assert table.other_mounts_of("ccab4aaf_frigate", "nas_media") == ("nas_config",)

    def test_an_unknown_addon_has_no_mount(self):
        table = build_mount_table(OPTIONS, [FRIGATE])
        assert table.mounts_for("core_ssh") == ()
        assert table.slugs_for("nas_backup") == ()


class TestOrderIsDeterministic:
    def test_slugs_are_sorted(self):
        """C'est dans cet ordre que repair.py prend ses verrous par add-on. Un
        ordre variable entre deux remédiations qui partagent partiellement leurs
        add-ons produirait un interblocage, visible seulement en production et
        seulement parfois."""
        table = build_mount_table(OPTIONS, [MOTIONEYE, FRIGATE])
        assert table.slugs_for("nas_media") == tuple(sorted(table.slugs_for("nas_media")))

    def test_the_declaration_order_does_not_change_the_result(self):
        assert build_mount_table(OPTIONS, [FRIGATE, MOTIONEYE]) == build_mount_table(
            OPTIONS, [MOTIONEYE, FRIGATE]
        )


class TestTheConfigurationCanBeIncoherent:
    """Les deux incohérences arrivent normalement pendant l'édition. Lever ici
    empêcherait l'entrée de se charger."""

    def test_a_mount_unknown_to_the_options_is_ignored(self):
        table = build_mount_table(OPTIONS, [{"slug": "a", "mounts": ["nas_media", "parti"]}])
        assert table.mounts_for("a") == ("nas_media",)

    def test_a_mount_no_addon_uses_is_left_out(self):
        """La séquence de réparation déplace des fichiers. Sans add-on, personne
        n'écrit de façon connue, et remuer /media/x parce qu'un montage est tombé
        serait une initiative que rien n'a demandée."""
        table = build_mount_table(OPTIONS, [MOTIONEYE])
        assert set(table.mounts) == {"nas_media"}

    def test_an_addon_whose_mounts_all_vanished_is_dropped(self):
        """Sinon other_mounts_of renverrait des noms que `mounts` ne connaît
        pas, et la garde de relance interrogerait un état inexistant."""
        table = build_mount_table(OPTIONS, [{"slug": "a", "mounts": ["parti"]}])
        assert table.by_addon == {}
        assert table.mounts == {}

    def test_a_mount_declared_twice_by_one_addon_is_deduplicated(self):
        """Sans cela il serait arrêté deux fois, et le compte d'add-ons affiché
        sur la carte serait faux."""
        table = build_mount_table(
            OPTIONS, [{"slug": "a", "mounts": ["nas_media", "nas_media"]}]
        )
        assert table.mounts_for("a") == ("nas_media",)
        assert table.slugs_for("nas_media") == ("a",)

    def test_a_subentry_without_slug_is_skipped(self):
        assert build_mount_table(OPTIONS, [{"mounts": ["nas_media"]}]).mounts == {}


class TestTheMountCarriesItsOwnConfiguration:
    def test_mode_and_host_come_from_the_mount_not_the_addon(self):
        """Un montage est un objet physique unique : il ne peut pas être réparé
        de deux façons parce que deux add-ons l'ont déclaré différemment. Le
        conflit n'est pas arbitré, il est rendu impossible."""
        table = build_mount_table(OPTIONS, [FRIGATE, MOTIONEYE])
        assert table.mounts["nas_media"].mode == "local_fallback"
        assert table.mounts["nas_config"].mode == "stop_only"
        assert table.mounts["nas_media"].host == "10.0.0.12"

    def test_the_path_is_derived_not_stored(self):
        table = build_mount_table(OPTIONS, [FRIGATE])
        assert table.mounts["nas_media"].path == "/media/nas_media"
        assert table.mounts["nas_config"].path == "/share/nas_config"
