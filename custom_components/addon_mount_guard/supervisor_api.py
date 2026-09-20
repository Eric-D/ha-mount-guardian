"""La seule porte vers le Supervisor.

Tout passe par ici, et pour deux raisons.

**Découpler.** `aiohasupervisor` est la bibliothèque officielle du Supervisor,
mais ses modèles sont les siens : des `StrEnum`, des `PurePath`, des dataclasses
à trente champs. Les laisser circuler dans le coordinator, la machine à états et
la séquence ferait dépendre tout le dépôt de leur forme. Ici on en extrait les
cinq champs qui nous intéressent, et le reste du code ne connaît que `Mount` et
`AddonInfo`.

**Rendre la séquence testable.** `repair.py` reçoit un objet conforme à
`SupervisorApi` ; les tests lui en passent un qui compte les appels. Sans cette
couture, tester l'arrêt puis la relance de trois add-ons demanderait de simuler
`hass` tout entier.

Le client vient de `homeassistant.components.hassio.get_supervisor_client`, qui
figure dans le `__all__` du composant — c'est le point d'entrée prévu pour les
intégrations tierces, et il est typé. **Ne pas revenir à
`hass.data["hassio"].send_command`** : c'est l'ancien client non typé, interne,
et il faut alors réécrire à la main le déballage de l'enveloppe et la carte des
chemins d'URL.

`aiohasupervisor` n'est **pas** déclaré dans `requirements`, et il ne doit pas
l'être : c'est une dépendance du **composant `hassio`**, que Home Assistant
installe au moment de le mettre en place. Notre `dependencies: ["hassio"]`
garantit que cette mise en place précède l'import de ce module.

Attention à la formulation exacte : ce n'est *pas* une dépendance du paquet
`homeassistant`. Elle figurait encore dans ses `requires_dist` en 2026.1.0 et en
est sortie depuis. L'y déclarer de notre côté imposerait une borne de version qui
entrerait tôt ou tard en conflit avec celle que `hassio` épingle, et pip
refuserait d'installer l'intégration.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any, Protocol

from aiohasupervisor.exceptions import SupervisorError as LibSupervisorError

from .const import SUPPORTED_USAGES

_LOGGER = logging.getLogger(__name__)


class SupervisorApiError(Exception):
    """Le Supervisor n'a pas répondu, ou a répondu autre chose que prévu.

    Nommée différemment de `aiohasupervisor.exceptions.SupervisorError` à
    dessein : les deux se croiseraient dans les imports, et rattraper la
    mauvaise ferait passer une panne de transport pour un bug de l'intégration.
    """


#: États d'add-on que le Supervisor considère comme « en marche ».
#:
#: `startup` compte, et c'est le piège : un add-on qui démarre encore n'est pas
#: arrêté. L'oublier ferait croire l'étape 1 terminée alors que Frigate ouvre
#: justement ses fichiers, et la mise de côté partirait sous ses pieds.
ADDON_RUNNING_STATES = ("started", "startup")

#: Le Supervisor annonce le montage actif. Ce n'est PAS la même chose que
#: « monté pour le conteneur core », et toute cette intégration existe parce que
#: les deux divergent : c'est `fileops.is_mounted` qui tranche.
MOUNT_STATE_ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class Mount:
    """Un stockage réseau, réduit à ce dont on se sert."""

    name: str
    usage: str
    type: str
    state: str | None
    server: str | None = None
    #: Chemin annoncé par le Supervisor (`/media/<nom>`, `/share/<nom>`). On le
    #: garde pour le recouper avec notre propre dérivation
    #: (`mount_table.mount_path`) : ce sont deux façons indépendantes d'obtenir
    #: la même chose, et leur désaccord signalerait que le Supervisor a changé
    #: sa disposition sous nos pieds. On ne s'en sert pas comme source unique,
    #: parce qu'il est absent tant que le montage n'a jamais été activé —
    #: exactement l'état dans lequel on a le plus besoin du chemin.
    user_path: str | None = None

    @property
    def supported(self) -> bool:
        """`backup` est exclu : voir SUPPORTED_USAGES."""
        return self.usage in SUPPORTED_USAGES

    @property
    def active(self) -> bool:
        return self.state == MOUNT_STATE_ACTIVE


@dataclass(frozen=True, slots=True)
class AddonInfo:
    slug: str
    name: str
    state: str

    @property
    def running(self) -> bool:
        return self.state in ADDON_RUNNING_STATES


class SupervisorApi(Protocol):
    """Le contrat que `repair.py` et le coordinator connaissent."""

    async def mounts(self) -> list[Mount]: ...

    async def reload_mount(self, name: str) -> None: ...

    async def addons(self) -> list[AddonInfo]: ...

    async def addon_info(self, slug: str) -> AddonInfo: ...

    async def start_addon(self, slug: str) -> None: ...

    async def stop_addon(self, slug: str) -> None: ...


def _text(value: Any) -> str | None:
    """Réduit un `StrEnum` ou un `PurePath` à sa chaîne.

    Pas `str(value)` directement : sur un `StrEnum`, `str()` rend bien la
    valeur, mais sur `None` il rendrait « None », qui passerait ensuite tous les
    tests de vérité et ferait comparer un état à la chaîne « None ».
    """
    if value is None:
        return None
    if isinstance(value, PurePath):
        return str(value)
    return str(value)


class HassioSupervisorApi:
    """Implémentation réelle, par-dessus le client officiel du Supervisor."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def mounts(self) -> list[Mount]:
        info = await self._guard("mounts.info", self._client.mounts.info())
        return [
            Mount(
                name=raw.name,
                usage=_text(raw.usage) or "",
                type=_text(raw.type) or "",
                state=_text(raw.state),
                server=getattr(raw, "server", None),
                user_path=_text(getattr(raw, "user_path", None)),
            )
            for raw in info.mounts
        ]

    async def reload_mount(self, name: str) -> None:
        await self._guard(f"reload_mount({name})", self._client.mounts.reload_mount(name))

    async def addons(self) -> list[AddonInfo]:
        installed = await self._guard("addons.list", self._client.addons.list())
        return [self._addon(raw) for raw in installed]

    async def addon_info(self, slug: str) -> AddonInfo:
        raw = await self._guard(f"addon_info({slug})", self._client.addons.addon_info(slug))
        return self._addon(raw)

    async def start_addon(self, slug: str) -> None:
        await self._guard(f"start_addon({slug})", self._client.addons.start_addon(slug))

    async def stop_addon(self, slug: str) -> None:
        await self._guard(f"stop_addon({slug})", self._client.addons.stop_addon(slug))

    @staticmethod
    def _addon(raw: Any) -> AddonInfo:
        return AddonInfo(
            slug=raw.slug,
            # Le nom peut manquer sur un add-on dont le dépôt a disparu. Afficher
            # le slug est moins beau qu'un nom, et infiniment plus utile qu'une
            # case vide sur la carte.
            name=getattr(raw, "name", None) or raw.slug,
            state=_text(raw.state) or "unknown",
        )

    @staticmethod
    async def _guard(what: str, awaitable: Any) -> Any:
        """Remet toute panne de transport sous un seul type.

        L'appelant n'a ainsi qu'une exception à rattraper, quelle que soit celle
        que l'amont choisira de lever la prochaine fois. `aiohasupervisor` en
        expose une dizaine — `SupervisorTimeoutError`, `SupervisorNotFoundError`,
        `SupervisorBadRequestError`… — toutes dérivées de `SupervisorError`, mais
        les énumérer chez l'appelant reviendrait à recopier leur hiérarchie dans
        trois fichiers.
        """
        try:
            return await awaitable
        except LibSupervisorError as err:
            raise SupervisorApiError(f"{what} : {err}") from err
        except Exception as err:  # volontairement large : voir la docstring
            raise SupervisorApiError(f"{what} : {err}") from err


def from_hass(hass: Any) -> HassioSupervisorApi:
    """Construit l'API à partir du client officiel du composant hassio.

    `dependencies: ["hassio"]` dans le manifeste est la vraie garde : Home
    Assistant refuse de mettre en place cette intégration si le composant n'est
    pas chargé, donc sur une installation Container ou Core l'entrée n'existe
    même pas. Ce qui suit ne rattrape que le cas résiduel — `hassio` chargé mais
    sans client — où il vaut mieux un message nommé qu'un `KeyError` opaque
    remonté depuis les entrailles d'un helper.
    """
    from homeassistant.components.hassio import get_supervisor_client

    try:
        return HassioSupervisorApi(get_supervisor_client(hass))
    except Exception as err:
        raise SupervisorApiError(
            "Superviseur introuvable : cette intégration demande Home Assistant OS "
            "ou Supervised."
        ) from err
