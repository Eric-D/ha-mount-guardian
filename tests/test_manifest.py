"""Gardes sur ce que hassfest ne valide pas.

hassfest (job « hassfest » de validate.yml) valide réellement le manifeste :
ordre des clés, vocabulaire d'`integration_type`, présence de « version » et la
règle « composant importé mais non déclaré ». Dupliquer ça ici avec des
assertions écrites à la main ne donnerait que des tautologies relisant le
fichier qu'on vient d'écrire.

Restent deux choses que hassfest ignore et qui ne se voient autrement qu'à
l'installation ou après publication : le plancher annoncé à HACS, et la
cohérence des numéros de version entre les fichiers que le workflow de release
met à jour par substitution.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components/addon_mount_guard"
MANIFEST = json.loads((COMPONENT / "manifest.json").read_text("utf-8"))
HACS = json.loads((ROOT / "hacs.json").read_text("utf-8"))


class TestHacsMinimumVersion:
    """`hacs.json` ne bloque que l'installation via HACS, rien d'autre.

    C'est un cliquet, pas une preuve : il empêche d'abaisser le plancher par
    inadvertance, mais il ne peut pas détecter qu'une API nouvellement utilisée
    exige plus récent.
    """

    def test_is_parsable(self):
        assert re.match(r"^\d+\.\d+", HACS["homeassistant"])

    def test_the_readme_announces_the_same_floor(self):
        """Le README est le seul endroit qu'un utilisateur lit avant
        d'installer, et rien d'autre ne croise les deux fichiers."""
        readme = (ROOT / "README.md").read_text("utf-8")
        major, minor = HACS["homeassistant"].split(".")[:2]
        assert f"**{major}.{minor}**" in readme

    def test_covers_the_apis_in_use(self):
        major, minor = (
            int(part) for part in re.match(r"^(\d+)\.(\d+)", HACS["homeassistant"]).groups()
        )
        assert (major, minor) >= (2026, 1), (
            f"plancher annoncé {HACS['homeassistant']} : trop bas. Politique de "
            "support : série 2026 uniquement. Les API employées exigent au minimum "
            "2025.2 (sous-entrées de configuration), 2024.12 (OptionsFlow."
            "config_entry), 2024.11 (getGridOptions) et 2024.7 "
            "(async_register_static_paths)."
        )


class TestTheManifestSaysWhatTheIntegrationIs:
    """Trois clés que hassfest accepte quelle que soit leur valeur, et dont
    chacune change le comportement pour l'utilisateur."""

    def test_it_declares_the_supervisor_dependency(self):
        """C'est la vraie garde contre une installation Container ou Core :
        Home Assistant refuse de mettre l'intégration en place si le composant
        n'est pas chargé, donc l'entrée n'existe même pas."""
        assert "hassio" in MANIFEST["dependencies"]

    def test_it_declares_every_component_it_imports(self):
        """hassfest attrape les imports directs, mais pas ceux d'un module
        qu'il ne suit pas. Le croisement explicite coûte trois lignes."""
        imported = set()
        for path in COMPONENT.glob("*.py"):
            imported |= set(
                re.findall(r"from homeassistant\.components import (\w+)", path.read_text("utf-8"))
            )
            imported |= set(
                re.findall(
                    r"from homeassistant\.components\.(\w+) import", path.read_text("utf-8")
                )
            )
        # `websocket_api`, `sensor`, `binary_sensor` et `button` sont des
        # dépendances implicites du cœur : hassfest ne les réclame pas.
        implicit = {"websocket_api", "sensor", "binary_sensor", "button"}
        assert imported - implicit <= set(MANIFEST["dependencies"])

    def test_only_one_entry_is_allowed(self):
        """Deux entrées surveilleraient les mêmes montages avec deux
        coordinators, deux séquences concurrentes et deux jeux de verrous —
        donc aucun verrou du tout."""
        assert MANIFEST["single_config_entry"] is True

    def test_it_has_no_runtime_requirement(self):
        """`aiohasupervisor` est installé par Home Assistant lui-même. L'y
        déclarer imposerait une borne qui entrerait en conflit avec celle du
        cœur, et pip refuserait d'installer l'intégration."""
        assert MANIFEST["requirements"] == []


class TestVersionsAreSynchronised:
    """Le workflow de release propage la version par substitution.

    Un `sed` qui ne matche plus échoue silencieusement et publie un paquet dont
    les versions divergent. Le cas le plus coûteux est `CARD_VERSION`, qui sert
    de cache-buster à la ressource Lovelace : désynchronisé, il fait resservir
    un module périmé derrière une URL fraîche.
    """

    def test_card_version_matches_manifest(self):
        from custom_components.addon_mount_guard import CARD_VERSION

        assert MANIFEST["version"] == CARD_VERSION

    def test_frontend_constant_matches_manifest(self):
        source = (ROOT / "frontend/src/version.ts").read_text("utf-8")
        match = re.search(r"export const MOUNT_GUARD_CARD_VERSION = '([^']+)';", source)
        assert match, "constante de version introuvable dans version.ts"
        assert match.group(1) == MANIFEST["version"]

    def test_package_json_matches_manifest(self):
        package = json.loads((ROOT / "frontend/package.json").read_text("utf-8"))
        assert package["version"] == MANIFEST["version"]

    def test_package_lock_matches_manifest(self):
        """`npm version` l'écrit à deux endroits, et il est commité par la
        release."""
        lock = json.loads((ROOT / "frontend/package-lock.json").read_text("utf-8"))
        assert lock["version"] == MANIFEST["version"]
        assert lock["packages"][""]["version"] == MANIFEST["version"]

    def test_committed_bundle_embeds_manifest_version(self):
        """Si le rebuild saute ou passe avant la substitution, la bannière du
        bundle annonce l'ancienne version tandis que l'URL porte la nouvelle :
        un module périmé servi derrière un cache-buster frais, exactement le
        symptôme que CARD_VERSION existe pour éviter."""
        bundle = (COMPONENT / "www/mount-guard-card.js").read_text("utf-8")
        assert f'"{MANIFEST["version"]}"' in bundle


class TestCardIsShipped:
    def test_the_bundle_is_committed(self):
        """Le paquet HACS ne contient que ce qui est dans le dépôt : un bundle
        absent donne une intégration qui se charge et une carte introuvable."""
        assert (COMPONENT / "www/mount-guard-card.js").is_file()

    def test_the_static_url_matches_the_file_name(self):
        """Ces deux-là sont écrits à deux endroits éloignés. Les désaccorder
        produit un 404 sur la ressource Lovelace, donc une carte définitivement
        en erreur, et rien d'autre ne le verrait."""
        from custom_components.addon_mount_guard import CARD_URL

        assert CARD_URL.endswith("/mount-guard-card.js")

    def test_the_bundle_embeds_no_external_url(self):
        """Aucune dépendance externe dans le bundle : pas de CDN, pas de police
        distante. La carte doit fonctionner en WebView Android, sur une
        installation sans accès Internet."""
        bundle = (COMPONENT / "www/mount-guard-card.js").read_text("utf-8")
        assert "http://" not in bundle.replace("http://www.w3.org", "")
        assert "cdn." not in bundle


class TestTheContractIsMirroredInTheBundle:
    def test_the_websocket_command_matches_the_backend(self):
        """Le nom de la commande est écrit des deux côtés. Les désaccorder
        ferait retomber la carte sur l'attribut du capteur en silence : elle
        marcherait, simplement une minute en retard, et personne ne saurait
        pourquoi."""
        from custom_components.addon_mount_guard.websocket_api import TYPE_SUBSCRIBE

        source = (ROOT / "frontend/src/helpers/subscribe.ts").read_text("utf-8")
        assert f"'{TYPE_SUBSCRIBE}'" in source

    def test_the_default_entity_matches_the_unique_id(self):
        """Le défaut de la carte doit être l'entité que l'intégration crée
        réellement, sinon la carte sortie du sélecteur est vide."""
        types_ts = (ROOT / "frontend/src/types.ts").read_text("utf-8")
        assert "'sensor.mount_guard_remediations'" in types_ts
