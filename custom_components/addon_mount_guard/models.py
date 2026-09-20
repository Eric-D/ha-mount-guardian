"""Le contrat de remédiation : une seule définition, côté Python.

C'est le seul objet que la carte connaisse. Il voyage par trois canaux — les
attributs de `sensor.mount_guard_remediations`, la commande WebSocket
`addon_mount_guard/subscribe`, et l'événement `addon_mount_guard_event` — et les
trois servent **le même** dictionnaire, produit par `to_wire`. Trois chemins qui
composeraient leur propre payload, c'est trois occasions d'en laisser un derrière
au premier champ ajouté, sans que rien ne devienne rouge.

Son miroir TypeScript vit dans `frontend/src/types.ts`, et
`tests/test_models.py` croise les deux : les clés de sortie et les littéraux des
unions doivent coïncider. Un état ajouté ici et oublié là-bas se rendrait en
pastille grise sans libellé, ce qu'aucun typage ne voit.

Ce module n'importe rien de Home Assistant : il est importable sous les mocks de
`tests/conftest.py`, et il doit le rester.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Any, Literal

# --- vocabulaire --------------------------------------------------------

MountState = Literal["ok", "degraded", "pending", "repairing"]

#: Dans l'ordre de gravité croissante, tel que la carte trie ses lignes.
#:
#: `degraded` et `pending` sont deux situations que l'on pourrait croire
#: identiques — le montage est tombé dans les deux cas — et les confondre est le
#: défaut que ce vocabulaire existe pour empêcher :
#:
#: - `degraded` : le NAS ne répond pas. L'add-on écrit en local et **c'est le
#:   comportement voulu** (`local_fallback`). Il n'y a rien à faire qu'attendre.
#: - `pending` : le NAS a répondu. La réparation est due mais n'a pas commencé,
#:   parce qu'un autre montage partageant les mêmes add-ons tient le verrou, ou
#:   parce qu'un réessai est programmé après un échec.
#:
#: Toute la gestion des add-ons partagés repose sur cette distinction : un
#: add-on est relancé en fin de séquence si ses autres montages sont `degraded`
#: (le repli local reprend, c'est ce qu'on veut), et retenu à l'arrêt si l'un
#: d'eux est `pending` ou `repairing` (il faudrait le rearrêter aussitôt).
MOUNT_STATES: tuple[str, ...] = ("ok", "degraded", "pending", "repairing")

#: Les états qui appellent une intervention. Voir `needs_remediation`.
ACTIONABLE_STATES: tuple[str, ...] = ("pending", "repairing")

Mode = Literal["local_fallback", "stop_only"]
MODES: tuple[str, ...] = ("local_fallback", "stop_only")

Step = Literal["stopping", "stashing", "reloading", "restoring", "rolling_back", "starting"]
STEPS: tuple[str, ...] = (
    "stopping",
    "stashing",
    "reloading",
    "restoring",
    "rolling_back",
    "starting",
)

#: Les étapes numérotées, par mode. Le nombre est publié dans `step_count` et la
#: carte le lit au lieu d'une constante locale : un stepper figé à cinq cases
#: afficherait trois étapes mortes en `stop_only`.
#: `stop_only` garde `reloading`, et ce n'est pas une inflation d'étapes. Le
#: Supervisor ne recharge PAS un montage tombé — c'est la raison d'être de cette
#: intégration. Sans cette étape, un montage en `stop_only` ne reviendrait
#: jamais et ses add-ons resteraient arrêtés indéfiniment. Ce que `stop_only`
#: retire, c'est le déplacement de fichiers : ni mise de côté, ni rapatriement.
STEPS_BY_MODE: dict[str, tuple[str, ...]] = {
    "local_fallback": ("stopping", "stashing", "reloading", "restoring", "starting"),
    "stop_only": ("stopping", "reloading", "starting"),
}

#: `rolling_back` ne figure dans aucune des deux séquences : ce n'est pas une
#: sixième étape mais l'échec de la quatrième, rendu en rouge à sa place. Il
#: porte donc le `step_index` de `restoring`.
ROLLBACK_REPLACES = "restoring"

AddonState = Literal["started", "stopped", "held", "unknown"]
#: `held` : arrêté, et maintenu arrêté parce qu'un AUTRE montage de cet add-on
#: attend sa réparation. Sans ce mot, la carte n'aurait à afficher qu'« arrêté »
#: sur un add-on que l'utilisateur vient de voir redémarrer ailleurs, sans rien
#: pour l'expliquer.
ADDON_STATES: tuple[str, ...] = ("started", "stopped", "held", "unknown")

#: Dix transitions gardées, la plus récente en tête. Le journal sert à
#: comprendre une panne qu'on n'a pas vue passer, pas à faire de l'histoire :
#: au-delà, il cesse d'être lisible sur une carte et commence à peser dans
#: chaque écriture d'attribut d'entité, donc dans le recorder.
HISTORY_LENGTH = 10

# --- clé de sérialisation ----------------------------------------------

#: Métadonnée portant le nom de la clé émise quand il diffère du nom de
#: l'attribut Python. Un seul cas, et il est imposé : `from` est un mot-clé
#: Python. Le renommage vit ici, dans la déclaration du champ, et non dans un
#: `to_wire` qui ferait un cas particulier — c'est la seule forme qui reste
#: juste quand un autre champ s'y ajoute.
_WIRE = "wire"


def _wire_name(f: Any) -> str:
    return f.metadata.get(_WIRE, f.name)


# --- le contrat ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RemediationAddon:
    """Un add-on tel que la carte l'affiche sur la ligne d'un montage."""

    slug: str
    name: str
    state: AddonState = "unknown"


@dataclass(frozen=True, slots=True)
class RemediationTransition:
    """Une entrée du journal.

    `at` est un instant UTC ISO 8601, comme tous les horodatages de ce contrat.
    Aucun délai n'est calculé côté Python — contrairement au dépôt dont ce
    dépôt reprend les conventions, où les dates étaient des jours civils et
    dépendaient donc du fuseau configuré dans Home Assistant. Ici ce sont des
    instants : la carte les soustrait à l'horloge du navigateur sans rien
    pouvoir décaler.
    """

    at: str
    from_: str = field(metadata={_WIRE: "from"})
    to: str = "ok"
    step: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Remediation:
    """L'état d'un montage, et la remédiation en cours s'il y en a une.

    Gelée et copiée à chaque changement (`dataclasses.replace`), jamais mutée.
    Muter en place laisserait l'état précédent référencer les mêmes objets :
    Home Assistant dédoublonne l'écriture d'état quand les attributs sont
    égaux, aucun `state_changed` ne serait émis, et la carte afficherait l'étape
    d'avant jusqu'au cycle suivant — soit une minute sur une séquence qui en
    dure deux.
    """

    mount: str
    path: str
    state: MountState = "ok"
    mode: Mode = "local_fallback"
    #: `None` hors remédiation. `step_index` vaut alors 0, ce qui distingue
    #: « pas commencé » de la première étape.
    step: Step | None = None
    step_index: int = 0
    #: Dérivé du mode et forcé par `__post_init__` : il ne peut pas mentir.
    step_count: int = 0
    started_at: str | None = None
    updated_at: str | None = None
    addons: tuple[RemediationAddon, ...] = ()
    files_total: int = 0
    files_done: int = 0
    bytes_total: int = 0
    bytes_done: int = 0
    #: Relatif à `path`, jamais absolu : la carte le tronque par la gauche et un
    #: préfixe commun de quarante caractères ne lui laisserait rien d'utile.
    current_file: str | None = None
    #: Renseigné seulement quand un réessai est effectivement programmé.
    next_retry_at: str | None = None
    last_error: str | None = None
    #: Dernier passage hors de `ok`. Survit à la réparation : c'est ce que lit
    #: le capteur « dernier incident », dont l'intérêt est justement de rester
    #: lisible une fois que tout est rentré dans l'ordre.
    last_incident_at: str | None = None
    history: tuple[RemediationTransition, ...] = ()

    def __post_init__(self) -> None:
        """Recale `step_index` et `step_count` sur `step` et `mode`.

        Ni l'un ni l'autre n'est une donnée indépendante : ce sont des
        dérivations, et les laisser libres les laisse mentir. Un
        `replace(mode=...)` changerait le mode sans changer le compte, et la
        carte dessinerait cinq cases pour une séquence qui en fait trois ; un
        `replace(step=...)` avancerait l'étape sans avancer son rang, et le
        stepper resterait allumé sur la précédente. Les deux sont invisibles au
        typage, aux tests de forme, et à la relecture.

        C'est aussi ce qui rend `dataclasses.replace` sûr partout ailleurs :
        aucun appelant n'a à se souvenir de recalculer quoi que ce soit.
        """
        object.__setattr__(self, "step_count", len(STEPS_BY_MODE[self.mode]))
        object.__setattr__(self, "step_index", step_index_of(self.mode, self.step))


# --- dérivations et sérialisation ---------------------------------------


def steps_for(mode: str) -> tuple[str, ...]:
    """Les étapes numérotées du mode, dans l'ordre."""
    return STEPS_BY_MODE[mode]


def step_index_of(mode: str, step: str | None) -> int:
    """Rang 1-based de l'étape, 0 hors séquence.

    `rolling_back` prend le rang de `restoring` : c'est l'échec de la même
    étape, pas une étape de plus.
    """
    if step is None:
        return 0
    if step == "rolling_back":
        step = ROLLBACK_REPLACES
    sequence = steps_for(mode)
    return sequence.index(step) + 1 if step in sequence else 0


def needs_remediation(remediation: Remediation) -> bool:
    """Ce montage réclame-t-il une intervention sur ses add-ons ?

    C'est LA question posée avant de relancer un add-on partagé par plusieurs
    montages. `degraded` répond non, et c'est le point à ne pas défaire : un
    montage dégradé dont le NAS est toujours absent est un repli assumé, ses
    add-ons doivent tourner en local. Répondre oui ici laisserait un add-on
    arrêté aussi longtemps que le second NAS resterait éteint, ce qui vide le
    mode `local_fallback` de son sens.
    """
    return remediation.state in ACTIONABLE_STATES


def to_wire(value: Any) -> Any:
    """Sérialise le contrat, et lui seul.

    Récursif et piloté par les champs déclarés : un champ ajouté à une
    dataclasse est émis sans rien toucher ici. `asdict` ferait presque la même
    chose, mais ignore la métadonnée qui renomme `from_` en `from`.
    """
    if isinstance(value, tuple | list):
        return [to_wire(item) for item in value]
    if hasattr(type(value), "__dataclass_fields__"):
        return {
            _wire_name(f): to_wire(getattr(value, f.name)) for f in fields(value)
        }
    return value


def wire_keys(cls: type) -> tuple[str, ...]:
    """Clés émises pour cette dataclasse, dans l'ordre de déclaration.

    Utilisée par `tests/test_models.py` pour croiser Python et TypeScript.
    """
    return tuple(_wire_name(f) for f in fields(cls))


def _pick(value: Any, allowed: tuple[str, ...], fallback: str) -> str:
    return value if value in allowed else fallback


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def from_wire(data: Any) -> Remediation | None:
    """Relit une remédiation persistée. `None` si elle n'est pas exploitable.

    Le `Store` de Home Assistant versionne le conteneur, pas le contenu : un
    état écrit par une version antérieure peut manquer de clés, ou en porter
    dont le vocabulaire a changé. Lever ici empêcherait l'intégration de se
    charger, et pour une donnée qu'on sait reconstruire — un cycle de polling
    suffit à retrouver l'état réel d'un montage.

    **Chaque champ est donc ramené dans son vocabulaire**, jamais recopié tel
    quel. Un `state` inconnu relu sans filtre se propagerait jusqu'à
    `needs_remediation`, qui répondrait non, et l'add-on repartirait au milieu
    d'une remédiation.
    """
    if not isinstance(data, dict):
        return None
    mount = data.get("mount")
    path = data.get("path")
    if not isinstance(mount, str) or not isinstance(path, str) or not mount:
        return None

    addons = tuple(
        RemediationAddon(
            slug=raw["slug"],
            name=raw.get("name") or raw["slug"],
            state=_pick(raw.get("state"), ADDON_STATES, "unknown"),  # type: ignore[arg-type]
        )
        for raw in data.get("addons", ())
        if isinstance(raw, dict) and isinstance(raw.get("slug"), str)
    )
    history = tuple(
        RemediationTransition(
            at=raw["at"],
            from_=_pick(raw.get("from"), MOUNT_STATES, "ok"),
            to=_pick(raw.get("to"), MOUNT_STATES, "ok"),
            step=_text_or_none(raw.get("step")),
            error=_text_or_none(raw.get("error")),
        )
        for raw in data.get("history", ())
        if isinstance(raw, dict) and isinstance(raw.get("at"), str)
    )[:HISTORY_LENGTH]

    step = data.get("step")
    step = step if step in STEPS else None
    mode = _pick(data.get("mode"), MODES, "local_fallback")
    return Remediation(
        mount=mount,
        path=path,
        state=_pick(data.get("state"), MOUNT_STATES, "ok"),  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        step=step,  # type: ignore[arg-type]
        # `step_index` n'est pas relu du tout : `__post_init__` le dérive de
        # `step` et du mode. Un couple incohérent venu du disque ne peut donc
        # pas faire pointer le stepper sur une étape qui n'est pas celle qui
        # tourne.
        started_at=_text_or_none(data.get("started_at")),
        updated_at=_text_or_none(data.get("updated_at")),
        addons=addons,
        files_total=_int(data.get("files_total")),
        files_done=_int(data.get("files_done")),
        bytes_total=_int(data.get("bytes_total")),
        bytes_done=_int(data.get("bytes_done")),
        current_file=_text_or_none(data.get("current_file")),
        next_retry_at=_text_or_none(data.get("next_retry_at")),
        last_error=_text_or_none(data.get("last_error")),
        last_incident_at=_text_or_none(data.get("last_incident_at")),
        history=history,
    )


def new_remediation(mount: str, path: str, mode: str = "local_fallback") -> Remediation:
    """Un montage sain, tel qu'on le découvre au chargement."""
    return Remediation(mount=mount, path=path, mode=mode)  # type: ignore[arg-type]


def with_progress(
    remediation: Remediation,
    *,
    files_done: int,
    bytes_done: int,
    current_file: str | None,
    updated_at: str,
) -> Remediation:
    """Copie avec la progression avancée. Voir la docstring de `Remediation`."""
    return replace(
        remediation,
        files_done=files_done,
        bytes_done=bytes_done,
        current_file=current_file,
        updated_at=updated_at,
    )
