"""Le NAS répond-il ?

C'est la question qui déclenche toute la séquence : tant qu'elle répond non, le
montage reste `degraded` et l'add-on écrit tranquillement en local. Une réponse
faussement positive arrête les add-ons pour rien et enchaîne les échecs ; une
réponse faussement négative laisse l'add-on écrire en local des heures après le
retour du NAS.

**Pas de ping ICMP.** Le conteneur core n'a pas toujours `CAP_NET_RAW`, et un
repli silencieux du ping vers le TCP rendrait le comportement dépendant de
l'installation : la même configuration se comporterait différemment chez deux
utilisateurs, et le diagnostic partirait dans le mur. Une connexion TCP sur le
port du protocole de partage est de toute façon un meilleur test — c'est ce port
précis que le montage va utiliser, et un NAS qui répond au ping pendant que Samba
démarre encore est exactement le cas qui fait échouer la réparation.

Module pur : rien de Home Assistant, et l'ouverture de connexion est injectable
pour que les tests n'aient besoin d'aucune socket.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .const import DEFAULT_PROBE_PORT, PROBE_PORTS, PROBE_TIMEOUT

_LOGGER = logging.getLogger(__name__)

Opener = Callable[[str, int], Awaitable[tuple[Any, Any]]]


def probe_port(mount_type: str | None) -> int:
    """Port à tester pour ce type de montage.

    Un type inconnu retombe sur 445 plutôt que de lever : le Supervisor peut
    gagner un type de partage sans nous prévenir, et refuser de tester
    laisserait le montage dégradé pour toujours. Se tromper de port fait au pire
    attendre le retour du NAS un peu plus longtemps.
    """
    return PROBE_PORTS.get((mount_type or "").lower(), DEFAULT_PROBE_PORT)


async def async_is_reachable(
    host: str,
    *,
    port: int,
    # Exemption ASYNC109 : la règle veut que le délai vienne de l'appelant, par un
    # `asyncio.timeout` qui l'enveloppe. Ici le délai EST la sémantique — un NAS
    # qui met huit secondes à accepter une connexion n'est pas joignable au sens
    # de cette intégration, et le remonter chez l'appelant obligerait chacun des
    # trois (polling, service `repair`, flux de configuration) à se souvenir de
    # le poser. L'un l'oublierait, et le polling se bloquerait sur le délai TCP
    # du noyau, soit deux minutes.
    timeout: float = PROBE_TIMEOUT,  # noqa: ASYNC109
    opener: Opener | None = None,
) -> bool:
    """Ouvre une connexion TCP, la referme, et dit si ça a marché.

    `asyncio.open_connection` et non `socket.connect` : le second bloque la
    boucle d'événements pendant tout le délai d'attente, soit trois secondes
    d'interface figée par montage et par cycle de polling. C'est précisément ce
    que la règle ASYNC de ruff verrouille.

    La connexion est **toujours** refermée, y compris sur délai dépassé : un
    writer laissé ouvert à chaque cycle finit par épuiser les descripteurs de
    fichiers du conteneur, et la panne qui en résulte ne ressemble en rien à sa
    cause.

    `wait_closed()` n'est volontairement pas attendu : la fermeture d'une socket
    de test n'a rien à nous apprendre, et un NAS à moitié réveillé peut ne jamais
    renvoyer son FIN — on rendrait alors la main bien après le délai qu'on vient
    de fixer.
    """
    open_connection = opener or asyncio.open_connection
    writer = None
    try:
        async with asyncio.timeout(timeout):
            _reader, writer = await open_connection(host, port)
    except TimeoutError:
        _LOGGER.debug("%s:%d injoignable (délai de %.1fs dépassé)", host, port, timeout)
        return False
    except OSError as err:
        _LOGGER.debug("%s:%d injoignable (%s)", host, port, err)
        return False
    finally:
        if writer is not None:
            writer.close()
    return True
