"""Croisement du flux de configuration et des fichiers de traduction.

`strings.json` n'est **jamais lu à l'exécution** pour une intégration
personnalisée : Home Assistant ne charge que `translations/<langue>.json`, avec
repli sur `en`. Une clé présente dans le seul `strings.json` s'affiche donc en
clé brute à l'utilisateur. Cette suite croise **tous** les fichiers, et il ne
faut pas la restreindre à `strings.json`.

`en.json` n'est pas optionnel : `en` est la langue de repli de Home Assistant,
donc ce que voit tout utilisateur non francophone.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components/addon_mount_guard"

FILES = {
    "strings.json": COMPONENT / "strings.json",
    "fr.json": COMPONENT / "translations/fr.json",
    "en.json": COMPONENT / "translations/en.json",
}


def _load(name: str) -> dict:
    return json.loads(FILES[name].read_text("utf-8"))


def _flatten(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _flatten(value, path)
        else:
            keys.add(path)
    return keys


@pytest.mark.parametrize("name", list(FILES))
class TestEveryFileIsComplete:
    def test_exists(self, name):
        assert FILES[name].is_file(), f"{name} manquant"

    def test_declares_the_config_and_options_steps(self, name):
        data = _load(name)
        assert set(data["config"]["step"]) == {"user"}
        assert set(data["options"]["step"]) == {"init"}

    def test_the_two_forms_declare_the_same_four_settings(self, name):
        """Un champ sans libellé s'affiche « min_free_ratio » à l'utilisateur."""
        expected = {"scan_interval", "retry_interval", "min_free_ratio", "notify"}
        data = _load(name)
        assert set(data["config"]["step"]["user"]["data"]) == expected
        assert set(data["options"]["step"]["init"]["data"]) == expected

    def test_declares_both_subentry_steps(self, name):
        steps = _load(name)["config_subentries"]["addon"]["step"]
        assert set(steps) == {"addon", "mounts"}

    def test_declares_every_field_of_the_mounts_step(self, name):
        data = _load(name)["config_subentries"]["addon"]["step"]["mounts"]["data"]
        assert set(data) == {"mounts", "host", "mode", "overwrite"}

    def test_declares_the_abort_reasons_the_subentry_flow_produces(self, name):
        aborts = _load(name)["config_subentries"]["addon"]["abort"]
        assert {"no_supervisor", "no_addons", "no_mounts"} <= set(aborts)

    def test_declares_the_error_the_config_flow_can_return(self, name):
        assert "no_supervisor" in _load(name)["config"]["error"]

    def test_declares_no_reauth_step(self, name):
        """Il n'y a rien à authentifier : le Superviseur répond au conteneur
        core sans identifiant, et le NAS n'est joint que par une socket TCP.
        Une étape de ré-authentification traduite serait le premier symptôme
        d'un copier-coller depuis un autre dépôt."""
        assert "reauth_confirm" not in _load(name)["config"]["step"]

    def test_the_repair_issue_is_described(self, name):
        """Ouverte par le coordinator après trois échecs. Sans traduction,
        l'utilisateur voit une réparation intitulée « repair_failed »."""
        issue = _load(name)["issues"]["repair_failed"]
        assert "{mount}" in issue["title"]
        assert "{error}" in issue["description"]


class TestSelectorsAreTranslated:
    """Les sélecteurs portent un `translation_key` : sans les options
    correspondantes, l'utilisateur choisit entre « local_fallback » et
    « stop_only » écrits tels quels."""

    @pytest.mark.parametrize("name", list(FILES))
    def test_every_mode_has_a_label(self, name):
        from custom_components.addon_mount_guard.models import MODES

        options = _load(name)["selector"]["mode"]["options"]
        assert set(options) == set(MODES)

    @pytest.mark.parametrize("name", list(FILES))
    def test_every_overwrite_policy_has_a_label(self, name):
        from custom_components.addon_mount_guard.const import OVERWRITE_MODES

        options = _load(name)["selector"]["overwrite"]["options"]
        assert set(options) == set(OVERWRITE_MODES)


class TestFilesAgreeWithEachOther:
    def test_fr_and_strings_have_the_same_keys(self):
        """`strings.json` n'est lu que par les outils ; `fr.json` est ce que
        voit l'utilisateur. Les laisser diverger, c'est traduire dans le vide."""
        assert _flatten(_load("strings.json")) == _flatten(_load("fr.json"))

    def test_en_has_the_same_keys_as_fr(self):
        assert _flatten(_load("en.json")) == _flatten(_load("fr.json"))

    def test_en_is_actually_translated(self):
        """Recopier `fr.json` sous le nom `en.json` fait passer les tests de
        clés et ne traduit rien."""
        assert (
            _load("en.json")["config"]["step"]["user"]["description"]
            != _load("fr.json")["config"]["step"]["user"]["description"]
        )


class TestServicesAreDescribed:
    def test_services_yaml_lists_exactly_the_registered_services(self):
        """Un service absent de services.yaml n'apparaît pas dans les outils de
        développement : l'utilisateur ne peut pas l'essayer avant de l'écrire
        dans une automatisation."""
        import yaml

        from custom_components.addon_mount_guard import (
            SERVICE_CANCEL,
            SERVICE_REPAIR,
            SERVICE_SET_MODE,
        )

        services = yaml.safe_load((COMPONENT / "services.yaml").read_text("utf-8"))
        assert set(services) == {SERVICE_REPAIR, SERVICE_CANCEL, SERVICE_SET_MODE}

    @pytest.mark.parametrize("name", list(FILES))
    def test_every_service_and_field_is_translated(self, name):
        import yaml

        services = yaml.safe_load((COMPONENT / "services.yaml").read_text("utf-8"))
        translated = _load(name)["services"]
        assert set(translated) == set(services)
        for service, spec in services.items():
            assert set(translated[service]["fields"]) == set(spec.get("fields", {})), service


#: Les clés de traduction réellement posées par les trois plateformes. Elles ne
#: sont pas importables sous les mocks — deux bases MagicMock lèvent un conflit
#: de métaclasse — donc elles sont relevées ici et recroisées avec leur source
#: par `TestThePlatformKeysExistInTheSource`.
ENTITY_KEYS = {
    "sensor": {"remediations", "addon_state", "pending_files", "last_incident"},
    "binary_sensor": {"mount_problem"},
    "button": {"repair"},
}


class TestEntityNamesAreTranslated:
    """`_attr_has_entity_name` + `translation_key` : sans les clés
    correspondantes, Home Assistant affiche la clé brute."""

    @pytest.mark.parametrize("name", list(FILES))
    def test_every_platform_declares_its_keys(self, name):
        entity = _load(name)["entity"]
        for platform, keys in ENTITY_KEYS.items():
            assert set(entity[platform]) == keys, platform

    @pytest.mark.parametrize("name", list(FILES))
    def test_the_addon_state_values_are_translated(self, name):
        """Sans ça, l'utilisateur lit « local » dans son tableau de bord."""
        from custom_components.addon_mount_guard.entities import (
            ADDON_LOCAL,
            ADDON_OK,
            ADDON_REPAIRING,
            ADDON_STOPPED,
        )

        states = _load(name)["entity"]["sensor"]["addon_state"]["state"]
        assert set(states) == {ADDON_OK, ADDON_LOCAL, ADDON_REPAIRING, ADDON_STOPPED}

    @pytest.mark.parametrize("name", list(FILES))
    def test_the_placeholders_match_what_the_platforms_pass(self, name):
        """`_attr_translation_placeholders = {"mount": ...}` : un nom qui
        n'utiliserait pas le placeholder donnerait autant d'entités
        homonymes sur le même appareil."""
        entity = _load(name)["entity"]
        assert "{mount}" in entity["binary_sensor"]["mount_problem"]["name"]
        assert "{mount}" in entity["button"]["repair"]["name"]


class TestThePlatformKeysExistInTheSource:
    """Croise la liste ci-dessus avec les fichiers de plateforme : une clé
    renommée dans le code et pas dans les traductions s'affiche en brut."""

    def test_every_declared_key_is_used_by_a_platform(self):
        for platform, keys in ENTITY_KEYS.items():
            source = (COMPONENT / f"{platform}.py").read_text("utf-8")
            for key in keys:
                assert f'"{key}"' in source, f"{platform}.{key}"
