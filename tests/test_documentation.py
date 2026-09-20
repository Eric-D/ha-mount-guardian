"""CLAUDE.md et la CI doivent décrire les mêmes vérifications.

Découvrir l'écart en poussant est exactement la friction que ce dépôt cherche à
supprimer ailleurs : un contributeur qui suit la documentation à la lettre doit
obtenir le même verdict que la CI.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAUDE = (ROOT / "CLAUDE.md").read_text("utf-8")
README = (ROOT / "README.md").read_text("utf-8")
VALIDATE = (ROOT / ".github/workflows/validate.yml").read_text("utf-8")


class TestTheCommandsAreDocumented:
    def test_every_ci_check_appears_in_claude_md(self):
        """Une vérification que la CI exécute et que la documentation tait est
        une vérification qu'on découvre en échec après avoir poussé."""
        for command in (
            "pytest",
            "ruff check .",
            "npm run typecheck",
            "npm run lint",
            "npm test",
            "npm run build",
        ):
            assert command in CLAUDE, f"{command!r} absent de CLAUDE.md"

    def test_the_bundle_check_is_documented(self):
        """La ligne qu'on oublie le plus souvent : le bundle commité doit
        correspondre au build, et la CI échoue sinon."""
        assert "git diff --exit-code" in CLAUDE
        assert "mount-guard-card.js" in CLAUDE

    def test_the_manifest_requirements_step_is_documented(self):
        """Elle produit un fichier vide aujourd'hui, et c'est justement ce qui
        la rend facile à supprimer — jusqu'au jour où une dépendance apparaît."""
        assert "scripts/manifest_requirements.py" in CLAUDE


class TestTheFloorIsConsistent:
    def test_the_python_versions_match_between_ci_and_doc(self):
        """Le plancher Python suit celui de Home Assistant. Le laisser diverger
        laisse passer une syntaxe qu'un utilisateur du plancher ne peut pas
        importer."""
        versions = set(re.findall(r'python-version: "(\d+\.\d+)"', VALIDATE))
        assert versions <= {"3.13", "3.14"}, versions
        for version in versions:
            assert version in CLAUDE, f"Python {version} absent de CLAUDE.md"

    def test_the_readme_and_claude_agree_on_the_floor(self):
        assert "2026.1" in CLAUDE and "**2026.1**" in README


class TestTheInvariantsAreWrittenDown:
    """Chacun de ces points a coûté du temps ou peut coûter des données. Sans
    la note, une refactorisation de bonne foi le défait en premier."""

    def test_the_card_loading_rule_is_documented(self):
        assert "add_extra_js_url" in CLAUDE
        assert "scoped-custom-element-registry" in CLAUDE

    def test_the_testability_rule_is_documented(self):
        """Pourquoi la logique ne vit pas dans sensor.py, et pourquoi le
        coordinator n'est pas hérité."""
        assert "métaclasse" in CLAUDE or "metaclass" in CLAUDE
        assert "DataUpdateCoordinator" in CLAUDE

    def test_the_stash_safety_rule_is_documented(self):
        """La pire panne que ce dépôt puisse produire."""
        assert "montage actif" in CLAUDE
        assert "contenu du NAS" in CLAUDE

    def test_the_degraded_versus_pending_rule_is_documented(self):
        """La distinction dont dépend toute la gestion des add-ons partagés."""
        assert "degraded" in CLAUDE and "pending" in CLAUDE
        assert "local_fallback" in CLAUDE

    def test_the_executor_rule_is_documented(self):
        assert "run_executor" in CLAUDE
        assert "asyncio.open_connection" in CLAUDE

    def test_the_masked_files_limitation_is_documented_for_users(self):
        """Elle appartient au README autant qu'au CLAUDE.md : c'est la seule
        chose que l'utilisateur doit savoir avant d'y compter."""
        assert "ERROR_MASKED_LOCAL_FILES" in CLAUDE
        assert "recouvert" in README or "masqué" in README


class TestTheReadmeDescribesWhatIsShipped:
    def test_every_service_is_documented(self):
        from custom_components.addon_mount_guard import (
            SERVICE_CANCEL,
            SERVICE_REPAIR,
            SERVICE_SET_MODE,
        )

        for service in (SERVICE_REPAIR, SERVICE_CANCEL, SERVICE_SET_MODE):
            assert f"addon_mount_guard.{service}" in README, service

    def test_the_event_is_documented(self):
        from custom_components.addon_mount_guard.const import EVENT_MOUNT_GUARD

        assert EVENT_MOUNT_GUARD in README

    def test_every_card_option_is_documented(self):
        """Une option non documentée n'existe pas : personne ne devine
        `show_history` en lisant la carte."""
        types_ts = (ROOT / "frontend/src/types.ts").read_text("utf-8")
        block = re.search(r"interface MountGuardConfig \{(.*?)\n\}", types_ts, re.DOTALL)
        assert block
        for option in re.findall(r"^\s*(\w+)\??:", block.group(1), re.MULTILINE):
            if option == "type":
                continue
            assert option in README, option

    def test_the_supervisor_only_limitation_is_stated(self):
        """C'est la première question de quelqu'un qui tourne en Container."""
        assert "Supervised" in README
