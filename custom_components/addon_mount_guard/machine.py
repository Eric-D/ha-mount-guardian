"""La machine à états d'un montage, et les deux règles qui en découlent.

Tout est pur : aucune E/S, aucun import de Home Assistant, aucune horloge —
`now` est toujours passé. C'est ce qui permet de tester la panne, le retour du
NAS, l'échec, le réessai et l'add-on partagé sans monter un seul système de
fichiers, et c'est ce qui doit rester vrai. Ce qui entre ici et fait un appel
réseau ou lit une date sort du périmètre des tests sans que rien ne le signale.

    ok ──(montage perdu)──► degraded ──(NAS joignable)──► pending
     ▲                         ▲   │                        │
     │                         │   └──(NAS reparti)─────────┘
     │                         │                            │
     │                    (échec, réessai programmé)   (verrou libre)
     │                         │                            ▼
     └─────────(succès)────────┴──────────────────────  repairing

`degraded` et `pending` ne se confondent pas, et c'est de cette distinction que
dépend toute la gestion des add-ons partagés — voir `plan_restart`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .models import (
    HISTORY_LENGTH,
    Remediation,
    RemediationTransition,
    needs_remediation,
)
from .mount_table import MountTable

#: Le montage s'est rétabli sans passer par la séquence de réparation.
#:
#: C'est le seul cas que cette intégration ne sait pas rattraper, et il faut le
#: dire plutôt que le taire. Pendant la panne, l'add-on a écrit dans le dossier
#: local sous le point de montage. La séquence met ces fichiers de côté **tant
#: que le montage est absent** (étape 2, avant le rechargement de l'étape 3) ;
#: si le montage revient avant, le bind mount les recouvre et ils deviennent
#: inaccessibles depuis le conteneur core. On ne peut pas démonter — aucun accès
#: à l'hôte, et le Supervisor n'expose pas l'opération.
#:
#: Le cas est rare : c'est précisément parce que le Supervisor ne recharge pas
#: un montage tombé que cette intégration existe. Il reste possible au
#: redémarrage de Home Assistant, qui rétablit les montages au passage.
ERROR_MASKED_LOCAL_FILES = (
    "Le montage s'est rétabli sans passer par la réparation : les fichiers "
    "écrits en local pendant la panne sont masqués sous le point de montage et "
    "n'ont pas pu être rapatriés."
)

_KEEP: object = object()


# --- transitions --------------------------------------------------------


def transition(
    remediation: Remediation,
    *,
    to: str,
    now: datetime,
    step: object = _KEEP,
    error: str | None = None,
    **changes: object,
) -> Remediation:
    """Change l'état et journalise. Renvoie une copie.

    **Seuls les changements d'état passent par ici**, pas les changements
    d'étape : une séquence réussie consommerait sinon cinq des dix entrées du
    journal, et il ne resterait rien de l'incident précédent — or c'est
    justement celui qu'on relit quand on cherche à comprendre. L'étape courante
    est déjà visible en direct dans `step` ; le journal sert à ce qui n'est plus
    sous les yeux. `enter_step` ne journalise donc pas.

    `last_error` est écrasé à chaque transition, `None` compris : une erreur qui
    survivrait à un retour en `ok` s'afficherait sur la carte d'un montage sain.
    """
    at = now.isoformat()
    next_step = remediation.step if step is _KEEP else step
    entry = RemediationTransition(
        at=at,
        from_=remediation.state,
        to=to,
        step=next_step,  # type: ignore[arg-type]
        error=error,
    )
    fields: dict[str, object] = {
        "state": to,
        "step": next_step,
        # Pas de `step_index` ici : `Remediation.__post_init__` le dérive.
        "updated_at": at,
        "last_error": error,
        # La plus récente en tête : c'est l'ordre d'affichage de la carte, et le
        # seul qui rende la troncature indolore.
        "history": (entry, *remediation.history)[:HISTORY_LENGTH],
    }
    if to != "ok" and remediation.state == "ok":
        # Horodaté à la sortie de `ok` et non à chaque transition : ce que lit
        # le capteur « dernier incident » est le début de la panne, pas le
        # dernier soubresaut de la réparation.
        fields["last_incident_at"] = at
    fields.update(changes)
    return replace(remediation, **fields)  # type: ignore[arg-type]


def enter_step(remediation: Remediation, step: str, *, now: datetime) -> Remediation:
    """Avance dans la séquence, sans toucher à l'état ni au journal."""
    return replace(
        remediation,
        step=step,  # type: ignore[arg-type]
        updated_at=now.isoformat(),
    )


# --- observation d'un cycle --------------------------------------------


def retry_due(remediation: Remediation, now: datetime) -> bool:
    """Le délai de réessai est-il écoulé ? Vrai si aucun n'était programmé."""
    if remediation.next_retry_at is None:
        return True
    return now >= datetime.fromisoformat(remediation.next_retry_at)


def observe(
    remediation: Remediation,
    *,
    mounted: bool,
    reachable: bool,
    now: datetime,
    stashed: bool = False,
) -> Remediation:
    """Applique un relevé à un montage. Renvoie une copie, ou l'original.

    `mounted` est ce que voit le **conteneur core** (`/proc/mounts`), pas ce que
    le Supervisor annonce : c'est tout l'objet de cette intégration que de
    traiter le cas où les deux divergent.

    `stashed` dit qu'un `<chemin>_local` attend d'être rapatrié. C'est l'état
    persistant qui survit à tout — redémarrage de Home Assistant compris — et
    c'est lui qui distingue les deux visages d'un montage revenu : avec des
    fichiers de côté, il reste du travail ; sans, c'est que le repli local est
    passé sous le point de montage et qu'on ne peut plus rien pour lui.

    Un montage en `repairing` n'est pas observé : c'est la séquence qui pilote,
    et un relevé arrivé au milieu de l'étape 3 verrait un montage absent qu'il
    vient lui-même de recharger.
    """
    if remediation.state == "repairing":
        return remediation

    if stashed and remediation.state != "pending" and retry_due(remediation, now):
        # Des fichiers attendent d'être rapatriés. Il faut une remédiation, que
        # le montage soit revenu ou non — c'est ce qui fait reprendre une
        # séquence interrompue par un redémarrage, sans avoir à savoir où elle
        # s'était arrêtée.
        return transition(remediation, to="pending", now=now, step=None, next_retry_at=None)

    if mounted:
        if remediation.state == "ok":
            return remediation
        # Revenu sans nous, et rien n'avait été mis de côté — `pending`
        # compris : une réparation qui démarrerait maintenant mettrait de côté
        # le contenu DU NAS, puisque c'est lui qu'on voit désormais sous le
        # point de montage. Voir
        # ERROR_MASKED_LOCAL_FILES : on ne peut plus rapatrier, on peut
        # seulement le dire.
        return transition(
            remediation,
            to="ok",
            now=now,
            step=None,
            error=ERROR_MASKED_LOCAL_FILES,
            next_retry_at=None,
        )

    if remediation.state == "ok":
        return transition(remediation, to="degraded", now=now, step=None)

    if remediation.state == "degraded":
        if reachable and retry_due(remediation, now):
            return transition(remediation, to="pending", now=now, next_retry_at=None)
        return remediation

    # pending : le NAS avait répondu. S'il ne répond plus, on retombe dans le
    # repli assumé — et les add-ons retenus à l'arrêt par ce `pending` sont
    # libérés du même coup, ce qui est exactement le comportement voulu.
    if not reachable:
        return transition(remediation, to="degraded", now=now)
    return remediation


def start_repair(remediation: Remediation, *, now: datetime) -> Remediation:
    """Entre dans la séquence. Remet les compteurs de progression à zéro.

    Les remettre ici et non à l'étape 4 : une remédiation qui a échoué en
    `restoring` garde sinon ses compteurs, et la carte affiche « 613 / 1284 »
    pendant l'étape 1 de la tentative suivante.
    """
    return transition(
        remediation,
        to="repairing",
        now=now,
        step=None,
        started_at=now.isoformat(),
        next_retry_at=None,
        files_total=0,
        files_done=0,
        bytes_total=0,
        bytes_done=0,
        current_file=None,
    )


def succeed(remediation: Remediation, *, now: datetime) -> Remediation:
    """Séquence terminée, montage actif."""
    return transition(
        remediation,
        to="ok",
        now=now,
        step=None,
        current_file=None,
        next_retry_at=None,
    )


def fail(
    remediation: Remediation, *, now: datetime, error: str, retry_interval: int
) -> Remediation:
    """Séquence interrompue : retour au repli local, réessai programmé.

    `degraded` et non `pending` : un réessai immédiat sur un NAS qui répond au
    TCP sans avoir fini d'exporter ses partages arrêterait et relancerait les
    add-ons en boucle. Et comme `degraded` ne retient pas les add-ons des autres
    montages, ceux-ci repartent en local pendant l'attente au lieu de rester
    arrêtés sans raison.
    """
    return transition(
        remediation,
        to="degraded",
        now=now,
        step=None,
        error=error,
        current_file=None,
        next_retry_at=(now + timedelta(seconds=retry_interval)).isoformat(),
    )


def consecutive_failures(remediation: Remediation) -> int:
    """Échecs d'affilée sur ce montage, lus dans le journal.

    Dérivé plutôt que compté à part : un compteur séparé peut être remis à zéro
    à un endroit et pas à l'autre, et l'écart ne se voit qu'au moment où la
    réparation Home Assistant s'ouvre — ou ne s'ouvre pas. Le journal, lui, est
    déjà la mémoire de ce qui s'est passé.

    Plafonné de fait par `HISTORY_LENGTH`, ce qui suffit très largement au seuil
    de trois.
    """
    count = 0
    for entry in remediation.history:
        if entry.to == "ok":
            break
        if entry.to == "degraded" and entry.error:
            count += 1
    return count


# --- les deux règles sur les add-ons partagés --------------------------


@dataclass(frozen=True, slots=True)
class RestartPlan:
    """Ce qu'on fait de chaque add-on à la fin d'une séquence."""

    start: tuple[str, ...]
    #: Arrêtés, et maintenus arrêtés : un autre de leurs montages attend sa
    #: réparation. C'est la dernière remédiation qui les libérera.
    held: tuple[str, ...]
    #: Qu'on n'a jamais arrêtés — l'utilisateur les avait arrêtés lui-même.
    untouched: tuple[str, ...]


def plan_restart(
    mount: str,
    table: MountTable,
    states: dict[str, Remediation],
    we_stopped: dict[str, bool],
) -> RestartPlan:
    """Qui a le droit de repartir à l'étape 5.

    Deux règles, et la première est celle qu'on inverse en croyant bien faire :

    1. **Un montage `degraded` ne retient personne.** Son NAS est absent,
       l'add-on doit repartir en local — c'est tout l'objet du mode
       `local_fallback`. Retenir l'add-on parce qu'un *autre* de ses montages
       est dégradé le laisserait arrêté aussi longtemps que le second NAS
       resterait éteint, et viderait le repli de son sens. Seuls `pending` et
       `repairing` retiennent, parce qu'eux vont devoir le rearrêter.
    2. **On ne relance que ce qu'on a arrêté.** Un add-on que l'utilisateur
       avait arrêté lui-même reste arrêté. `we_stopped` est tenu par le
       coordinator et non par la remédiation : la remédiation de `nas_config`
       ne sait pas que c'est celle de `nas_media` qui a arrêté Frigate.

    Le regroupement tombe tout seul de la règle 1 : deux montages du même add-on
    qui reviennent ensemble donnent **un** arrêt et **une** relance. Le premier
    ne relance pas (le second est `pending`), le second trouve l'add-on déjà
    arrêté et le relance en sortant. Il n'y a pas de mécanisme de lot, et il n'y
    en a pas besoin.
    """
    start: list[str] = []
    held: list[str] = []
    untouched: list[str] = []

    for slug in table.slugs_for(mount):
        if not we_stopped.get(slug, False):
            untouched.append(slug)
            continue
        others = table.other_mounts_of(slug, mount)
        if any(
            needs_remediation(states[other]) for other in others if other in states
        ):
            held.append(slug)
        else:
            start.append(slug)

    return RestartPlan(tuple(start), tuple(held), tuple(untouched))


def disk_guard(
    remediation: Remediation, *, free_ratio: float, threshold: float
) -> tuple[str, ...]:
    """Add-ons à arrêter parce que le disque local se remplit.

    Ne s'applique qu'en `degraded`, le seul état où un add-on écrit en local
    sans surveillance. En `repairing`, ils sont déjà arrêtés ; en `ok`, ils
    écrivent sur le NAS et l'espace local ne les concerne pas.

    Un seuil à 0 désactive le garde-fou : c'est la seule façon de refuser ce
    comportement sans désinstaller l'intégration, et il vaut mieux qu'elle tienne
    dans le même réglage que dans une case à cocher de plus.
    """
    if threshold <= 0 or remediation.state != "degraded" or free_ratio >= threshold:
        return ()
    # Seuls ceux qui tournent encore : renvoyer les autres ferait émettre des
    # arrêts sans effet à chaque cycle de polling, donc une ligne de journal
    # toutes les soixante secondes jusqu'au retour du NAS.
    return tuple(addon.slug for addon in remediation.addons if addon.state == "started")
