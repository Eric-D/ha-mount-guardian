"""Fixtures et mocks pour les tests de l'intégration Add-on Mount Guard.

Les tests doivent pouvoir tourner sans installer Home Assistant, qui est une
dépendance lourde et dont on ne teste rien ici : seules la machine à états, la
table inversée, la séquence de réparation et les opérations de fichiers sont
sous test.

On installe donc un chercheur de modules qui fabrique un MagicMock pour tout
import de `homeassistant.*` ou `voluptuous`. Une liste figée de modules à mocker
casse au premier import ajouté ; le chercheur, lui, encaisse — et
`test_imports.py` rend visible ce qu'il a fabriqué.

Le chercheur n'est installé que si le vrai paquet est absent, pour qu'un
environnement où Home Assistant est réellement installé continue de l'utiliser.

**Ce que ce harnais ne peut pas faire, et qui commande l'architecture du
dépôt :** un MagicMock ne se laisse pas hériter utilement. Deux bases mockées
lèvent `TypeError: metaclass conflict` — c'est le cas de
`class _GuardEntity(CoordinatorEntity, SensorEntity)`. Une seule base mockée est
pire : la « classe » obtenue *est* un MagicMock, elle s'importe, s'instancie, et
toutes ses méthodes sont muettes. Aucune erreur, CI verte, code jamais exécuté.
C'est pourquoi **aucun module testable ne dérive de `DataUpdateCoordinator`** :
le coordinator est instancié à l'exécution dans `__init__.py` (un appel, pas un
héritage) et toute la logique vit dans des classes ordinaires.
"""
from __future__ import annotations

import importlib.abc
import importlib.util
import sys
from unittest.mock import MagicMock

import pytest

# `aiohasupervisor` est la bibliothèque officielle du Supervisor. Elle est
# installée par Home Assistant lui-même, jamais par nous — d'où son absence du
# manifeste — donc elle manque dans l'environnement de test, qui n'installe pas
# Home Assistant.
_MOCK_ROOTS = ("homeassistant", "voluptuous", "aiohasupervisor")

# Tout module fabriqué est enregistré ici. Le finder fait réussir n'importe quel
# import sous ces racines, y compris une faute de frappe ou un helper retiré :
# sans trace, la CI resterait verte pendant que l'intégration ne se charge plus
# chez l'utilisateur. test_imports.py compare cet ensemble à une liste attendue,
# ce qui rend un nouvel import visible sans bloquer la suite.
MOCKED_MODULES: set[str] = set()

# Racines effectivement simulées. Vide quand les vrais paquets sont installés —
# notamment dans le job « import-check » de la CI. Les gardes de test_imports.py
# s'y adaptent au lieu d'échouer pour une raison bidon.
MOCKED_ROOTS: set[str] = set()


class _MockLoader(importlib.abc.Loader):
    """Fabrique un module factice qui accepte n'importe quel attribut."""

    def create_module(self, spec):
        MOCKED_MODULES.add(spec.name)
        module = MagicMock(name=spec.name)
        module.__name__ = spec.name
        module.__spec__ = spec
        module.__loader__ = self
        # __path__ fait du mock un paquet : sans lui, importer un sous-module
        # lève « X is not a package ».
        module.__path__ = []
        return module

    def exec_module(self, module):
        """Rien à exécuter : le module est déjà complet."""


class _MockFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root: str) -> None:
        self._root = root

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self._root or fullname.startswith(f"{self._root}."):
            return importlib.util.spec_from_loader(fullname, _MockLoader(), is_package=True)
        return None


for _root in _MOCK_ROOTS:
    try:
        __import__(_root)
    except ImportError:
        sys.meta_path.insert(0, _MockFinder(_root))
        MOCKED_ROOTS.add(_root)


@pytest.fixture
def mocked_ha_modules() -> set[str]:
    """Modules Home Assistant effectivement fabriqués par le finder."""
    return MOCKED_MODULES


@pytest.fixture
def mocked_roots() -> set[str]:
    """Racines simulées. Vide si les vrais paquets sont installés."""
    return MOCKED_ROOTS


# Vraies classes d'exception dans le module simulé.
#
# Un MagicMock ne peut pas être levé (« exceptions must derive from
# BaseException »), donc tout code de production qui lève rendait sa fonction
# intestable — et le harnais donnait 100 % de vert sur du câblage faux.
if "homeassistant" in MOCKED_ROOTS:
    import homeassistant.exceptions as _ha_exceptions

    class HomeAssistantError(Exception):
        """Équivalent local de homeassistant.exceptions.HomeAssistantError."""

    class ServiceValidationError(HomeAssistantError):
        """Équivalent local de ServiceValidationError."""

    _ha_exceptions.HomeAssistantError = HomeAssistantError
    _ha_exceptions.ServiceValidationError = ServiceValidationError

    # Pas de ConfigEntryAuthFailed, et ce n'est pas un oubli : il n'y a rien à
    # authentifier. Le Supervisor répond au conteneur core sans identifiant, et
    # le NAS n'est joint que par une socket TCP ouverte puis refermée. Lever une
    # erreur d'authentification afficherait à l'utilisateur une notification
    # « Reconfigurer » devant laquelle il n'aurait rien à saisir.

    import homeassistant.core as _ha_core

    def callback(func):
        """Décorateur identité, comme celui de Home Assistant.

        Un MagicMock remplace la fonction décorée au lieu de la renvoyer : tout
        code marqué @callback devenait alors intestable, et le harnais rendait
        du vert sur du code qui ne s'exécutait jamais.
        """
        func._hass_callback = True
        return func

    _ha_core.callback = callback

    # UpdateFailed ne vit pas dans homeassistant.exceptions mais dans le helper
    # du coordinator, et n'en hérite pas non plus : le coordinator la rattrape
    # par son type exact pour marquer l'échec du cycle.
    import homeassistant.helpers.update_coordinator as _ha_coordinator

    class UpdateFailed(Exception):
        """Équivalent local de update_coordinator.UpdateFailed."""

    _ha_coordinator.UpdateFailed = UpdateFailed

if "aiohasupervisor" in MOCKED_ROOTS:
    import aiohasupervisor.exceptions as _ahs_exceptions

    class SupervisorError(Exception):
        """Équivalent local de aiohasupervisor.exceptions.SupervisorError.

        Même raison que les autres : `supervisor_api.py` l'attrape par son type,
        et un MagicMock dans une clause `except` lève « catching classes that do
        not inherit from BaseException is not allowed ». Sans cette classe, tout
        le module deviendrait intestable — et la suite resterait verte.
        """

    _ahs_exceptions.SupervisorError = SupervisorError
