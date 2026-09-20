"""Ce que les entités affichent, dérivé du contrat de remédiation.

`sensor.py`, `binary_sensor.py` et `button.py` ne sont **pas importables** sous
les mocks de `tests/conftest.py` : `class X(CoordinatorEntity, SensorEntity)`
lève `TypeError: metaclass conflict` quand les deux bases sont des MagicMock.
Tout ce qui y vivrait serait hors de portée de la suite, et le rester
silencieusement.

Ce module porte donc l'intégralité de leur logique — identifiants, agrégation
par add-on, disponibilité des boutons — et les trois plateformes ne sont que des
enveloppes. **Ne pas y remettre de calcul** : un capteur qui compte mal ne lève
pas, il affiche simplement un chiffre faux, et personne ne le remarque avant
d'en avoir besoin.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .const import DOMAIN
from .models import Remediation

#: Vocabulaire du capteur d'état d'un add-on. Distinct de `MountState` à
#: dessein : un add-on n'a pas d'état de montage, il a une situation vis-à-vis
#: de l'ensemble de ses montages.
ADDON_OK = "ok"
ADDON_LOCAL = "local"
ADDON_REPAIRING = "repairing"
ADDON_STOPPED = "stopped"


def addon_identifier(entry_id: str, slug: str) -> tuple[str, str]:
    """Identifiant d'appareil d'un add-on surveillé.

    Dérivé de l'`entry_id` et du **slug**, jamais d'un réglage : un identifiant
    qui dépend d'une option signifie qu'en changer crée un appareil neuf et
    orpheline l'ancien, avec son historique et les automatisations qui le
    visaient.
    """
    return (DOMAIN, f"{entry_id}_addon_{slug}")


def mount_identifier(entry_id: str, mount: str) -> tuple[str, str]:
    """Identifiant d'appareil d'un stockage réseau.

    Le nom du montage ne se change pas : le renommer dans Home Assistant crée
    un autre montage, et le nôtre disparaît de la table — le comportement
    voulu, et la raison pour laquelle on peut s'en servir ici.
    """
    return (DOMAIN, f"{entry_id}_mount_{mount}")


def _for(states: Mapping[str, Remediation], mounts: Iterable[str]) -> list[Remediation]:
    return [states[name] for name in mounts if name in states]


def addon_state(states: Mapping[str, Remediation], slug: str, mounts: Iterable[str]) -> str:
    """Situation d'un add-on vis-à-vis de l'ensemble de ses montages.

    L'ordre de précédence n'est pas arbitraire : il dit ce qui mérite d'être
    affiché quand plusieurs choses sont vraies à la fois.

    1. `repairing` — quelque chose se passe, c'est ce qu'on veut voir.
    2. `stopped` — l'add-on ne tourne pas ; c'est plus grave que d'écrire en
       local, et c'est l'information que l'utilisateur cherche quand sa caméra
       n'enregistre plus.
    3. `local` — il tourne, mais écrit à côté du NAS. Le repli assumé.
    4. `ok`.

    Inverser 2 et 3 afficherait « local » sur un add-on arrêté, ce qui est faux
    de la pire façon : rassurant.
    """
    remediations = _for(states, mounts)
    if not remediations:
        return ADDON_OK
    if any(rem.state in ("pending", "repairing") for rem in remediations):
        return ADDON_REPAIRING
    for rem in remediations:
        for addon in rem.addons:
            if addon.slug == slug and addon.state in ("stopped", "held"):
                return ADDON_STOPPED
    if any(rem.state == "degraded" for rem in remediations):
        return ADDON_LOCAL
    return ADDON_OK


def pending_files(states: Mapping[str, Remediation], mounts: Iterable[str]) -> int:
    """Fichiers restant à rapatrier, tous montages confondus.

    `files_total - files_done` et non `files_total` : pendant un rapatriement,
    c'est ce qui reste qui intéresse, et le total ne bougerait pas d'un poil
    pendant que la barre avance.
    """
    return sum(
        max(rem.files_total - rem.files_done, 0) for rem in _for(states, mounts)
    )


def last_incident(states: Mapping[str, Remediation], mounts: Iterable[str]) -> str | None:
    """Horodatage du dernier incident, le plus récent des montages.

    Les chaînes ISO 8601 en UTC se comparent dans l'ordre chronologique — c'est
    une propriété du format, pas un hasard, et elle évite de reconstruire des
    `datetime` pour un `max`.
    """
    stamps = [rem.last_incident_at for rem in _for(states, mounts) if rem.last_incident_at]
    return max(stamps) if stamps else None


def has_problem(remediation: Remediation | None) -> bool:
    """Valeur du `binary_sensor` d'un montage (device_class `problem`).

    `pending` compte comme un problème : le NAS est revenu mais le montage
    n'est pas encore rétabli, et les add-ons sont retenus à l'arrêt. Le
    compter sain ferait clignoter le capteur au vert au milieu d'une panne.
    """
    return remediation is not None and remediation.state != "ok"


def repair_available(remediation: Remediation | None) -> bool:
    """Le bouton « Réparer maintenant » est-il utile ?

    Seulement quand il y a quelque chose à réparer. Un bouton actif sur un
    montage sain déclencherait une séquence qui arrête les add-ons, met de côté
    — et sur un montage actif, `repair.py` refuse de mettre de côté, donc elle
    ne casserait rien, mais elle arrêterait Frigate pour rien.
    """
    return remediation is not None and remediation.state in ("degraded", "pending")


def cancel_available(remediation: Remediation | None) -> bool:
    """L'annulation n'a de sens que pendant une séquence."""
    return remediation is not None and remediation.state == "repairing"


def active_remediations(states: Mapping[str, Remediation]) -> int:
    """État du capteur global : le nombre de remédiations en cours.

    `pending` compte : la réparation est décidée, elle attend un verrou ou son
    délai. L'exclure ferait retomber le compteur à zéro entre deux montages
    d'un même add-on qui se réparent l'un après l'autre, et une automatisation
    branchée dessus croirait que tout est fini.
    """
    return sum(1 for rem in states.values() if rem.state in ("pending", "repairing"))
