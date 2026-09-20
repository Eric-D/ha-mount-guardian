"""Ce que le finder de `conftest.py` fabrique doit rester visible, et les
modules testables doivent le rester.

Le finder fait réussir **n'importe quel** import sous `homeassistant.` ou
`voluptuous`, y compris une faute de frappe ou un helper retiré de l'amont.
Sans trace, la CI resterait verte pendant que l'intégration ne se charge plus
chez l'utilisateur. Cette suite compare l'ensemble effectivement fabriqué à une
liste attendue : un nouvel import devient visible sans bloquer la suite.

Le job `import-check` de la CI installe, lui, le vrai paquet — c'est le seul
endroit où l'existence des modules est réellement vérifiée.
"""
from __future__ import annotations

import importlib

# Importés pour leur effet de bord : c'est l'import qui peuple MOCKED_MODULES.
import custom_components.addon_mount_guard
import custom_components.addon_mount_guard.const
import custom_components.addon_mount_guard.coordinator
import custom_components.addon_mount_guard.entities
import custom_components.addon_mount_guard.fileops
import custom_components.addon_mount_guard.machine
import custom_components.addon_mount_guard.models
import custom_components.addon_mount_guard.mount_table
import custom_components.addon_mount_guard.reachability
import custom_components.addon_mount_guard.repair
import custom_components.addon_mount_guard.supervisor_api  # noqa: F401

# Les modules Home Assistant fabriqués par le finder pendant la suite.
#
# Ceux-ci ne viennent PAS de l'intégration : `conftest.py` les importe lui-même
# pour y poser de vraies classes d'exception et un vrai décorateur `@callback`.
# `models.py` et `const.py` n'importent rien de Home Assistant, délibérément —
# c'est ce qui les rend testables sans aucun mock. La liste grandira quand
# `coordinator.py` et consorts arriveront.
EXPECTED_ROOTS: set[str] = {
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.frontend",
    "homeassistant.components.http",
    "homeassistant.components.persistent_notification",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.issue_registry",
    "homeassistant.helpers.start",
    "homeassistant.helpers.storage",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "homeassistant.util.dt",
}

#: Les modules qui portent la logique, et qui doivent rester importables sous
#: les mocks. Voir la classe ci-dessous pour la raison.
TESTABLE_MODULES = (
    "",
    "const",
    "models",
    "mount_table",
    "machine",
    "supervisor_api",
    "reachability",
    "fileops",
    "repair",
    "coordinator",
    "entities",
)

#: Ceux qui ne le sont pas, et pourquoi. La liste est documentaire : rien ne
#: l'exécute, mais elle est le seul endroit où l'on puisse relire d'un coup
#: quelle logique est hors de portée de la suite.
#:
#: - `sensor`, `binary_sensor`, `button` : `class X(CoordinatorEntity, XEntity)`
#:   lève `TypeError: metaclass conflict` quand les deux bases sont des
#:   MagicMock.
#: - `config_flow` : dérive de `ConfigFlow`. Une base mockée unique ne lève
#:   pas — elle produit une « classe » qui *est* un MagicMock, muette et verte.
#: - `websocket_api` : ses fonctions sont décorées par
#:   `@websocket_api.websocket_command`, mocké, qui les remplace par un
#:   MagicMock. Le module s'importe ; ce qu'il contient ne s'exécute jamais.
NOT_IMPORTABLE = ("sensor", "binary_sensor", "button", "config_flow", "websocket_api")


def _module_name(suffix: str) -> str:
    """Le paquet lui-même quand le suffixe est vide : `__init__.py` porte les
    services et le câblage, et il doit rester importable comme les autres."""
    base = "custom_components.addon_mount_guard"
    return f"{base}.{suffix}" if suffix else base


class TestMockedModules:
    def test_no_unexpected_module_is_fabricated(self, mocked_ha_modules, mocked_roots):
        """Un import inattendu signale soit une dépendance nouvelle à
        documenter, soit une faute de frappe que le finder vient d'avaler."""
        if not mocked_roots:
            return  # les vrais paquets sont installés : rien n'est fabriqué
        unexpected = {
            name for name in mocked_ha_modules if name.startswith("homeassistant")
        } - EXPECTED_ROOTS
        assert not unexpected, (
            f"modules Home Assistant inattendus : {sorted(unexpected)}. "
            "Ajoutez-les à EXPECTED_ROOTS si c'est voulu."
        )


class TestTestableModulesStayImportable:
    """La propriété qui donne sa valeur à toute la suite.

    Le jour où l'un de ces modules importe `SensorEntity` ou dérive de
    `DataUpdateCoordinator`, il cesse d'être utilisable sous les mocks — et
    **tous** ses tests disparaissent de la collecte sans qu'aucun ne devienne
    rouge. C'est le seul garde-fou contre ça.
    """

    def test_every_logic_module_imports_under_the_mocks(self):
        for name in TESTABLE_MODULES:
            module = importlib.import_module(_module_name(name))
            assert module is not None, name

    def test_they_are_real_modules_and_not_mocks(self):
        """Un module fabriqué par le finder s'importe aussi, et sans erreur.
        Vérifier qu'il a bien un fichier source écarte le cas où un module
        testable aurait été renommé : l'import réussirait, et la suite le
        croirait sain."""
        for name in TESTABLE_MODULES:
            module = importlib.import_module(_module_name(name))
            expected = f"{name or '__init__'}.py"
            assert getattr(module, "__file__", "").endswith(expected), name
