"""Tout ce qui touche au disque. Synchrone, et appelé depuis un executor.

**Aucune de ces fonctions ne doit être appelée depuis la boucle d'événements.**
Un rapatriement de neuf gigaoctets y gèlerait Home Assistant entier — interface
comprise — pendant toute la copie. Elles sont volontairement écrites en
synchrone plutôt qu'en `async` trompeusement : une fonction `async` qui appelle
`shutil.copy2` ment sur ce qu'elle fait, et personne ne se demande plus où elle
tourne. Ici la signature dit « je bloque », et `repair.py` reçoit un
`run_executor` par lequel tout passe.

Deux règles de sûreté traversent le module :

- **on ne détruit jamais rien pour résoudre une collision.** Un fichier en trop
  se range à côté sous un autre nom ; un fichier écrasé ne revient pas.
- **la source n'est supprimée qu'après un parcours complet et sans erreur.**
  Une reprise après coupure recopie ce qui a déjà été copié — c'est gratuit,
  grâce à la comparaison des dates — alors qu'une source supprimée au fil de
  l'eau laisse, après une coupure, la moitié des fichiers nulle part.
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

from .const import (
    DEFAULT_CONCURRENCY,
    DEFAULT_OVERWRITE,
    OVERWRITE_ALWAYS,
    OVERWRITE_NEVER,
    STASH_SUFFIX,
)

_LOGGER = logging.getLogger(__name__)


def stash_dir(path: Path) -> Path:
    """Le répertoire de mise de côté, **frère** du point de montage.

    Frère et non enfant, et c'est le choix qui rend la reprise possible : le
    bind mount recouvre le point de montage, pas son voisin. Un `_local` placé
    dessous disparaîtrait de la vue au rechargement de l'étape 3, avec tout ce
    qu'on venait d'y mettre.

    Frère aussi parce qu'il est alors sur le même système de fichiers : les
    déplacements sont des renommages instantanés, pas des copies. Mettre de côté
    neuf gigaoctets prend quelques millisecondes.
    """
    return path.with_name(path.name + STASH_SUFFIX)


# --- lecture ------------------------------------------------------------


def is_mounted(path: Path, proc_mounts: Path = Path("/proc/mounts")) -> bool:
    """Ce chemin est-il un point de montage **pour le conteneur core** ?

    C'est la seule source de vérité qui compte. `GET /mounts` dit ce que le
    Supervisor croit avoir fait ; `/proc/mounts` dit ce que voit le processus
    qui écrit. Toute cette intégration existe parce que les deux divergent.

    `os.path.ismount()` ne suffit pas : il compare le numéro de périphérique du
    répertoire à celui de son parent, ce qui répond faux pour un bind mount
    issu du même système de fichiers — exactement notre cas.
    """
    target = str(path)
    try:
        content = proc_mounts.read_text("utf-8")
    except OSError as err:
        # Ni HA OS ni Supervised, ou /proc non monté. On ne peut rien affirmer :
        # répondre « non monté » déclencherait une réparation sur une
        # installation où il n'y a rien à réparer.
        _LOGGER.warning("Lecture de %s impossible (%s) : montage supposé actif", proc_mounts, err)
        return True
    for line in content.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        # Les espaces et quelques autres caractères sont échappés en octal par
        # le noyau. Sans ce décodage, un partage nommé « mes films » ne serait
        # jamais reconnu comme monté, et l'intégration le réparerait en boucle.
        if _unescape(fields[1]) == target:
            return True
    return False


def _unescape(field: str) -> str:
    """Décode les échappements octaux de /proc/mounts (\\040, \\011, \\012, \\134)."""
    for code, char in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        field = field.replace(code, char)
    return field


def free_ratio(path: Path) -> float:
    """Part d'espace libre du système de fichiers qui porte ce chemin, 0 à 1.

    En cas d'erreur, 1.0 — « tout va bien ». Renvoyer 0 ferait déclencher le
    garde-fou d'espace disque et arrêterait les add-ons sur une simple erreur de
    lecture, ce qui est exactement l'inverse de ce qu'on veut d'un garde-fou.
    """
    try:
        usage = shutil.disk_usage(path)
    except OSError as err:
        _LOGGER.warning("Espace disque illisible sur %s (%s)", path, err)
        return 1.0
    return usage.free / usage.total if usage.total else 1.0


def iter_files(root: Path) -> Iterator[Path]:
    """Tous les fichiers sous `root`, dans un ordre stable.

    Trié : la progression affichée sur la carte doit avancer de la même façon
    d'une reprise à l'autre, sans quoi le fichier courant sautille et donne
    l'impression que la copie recommence.

    Les liens symboliques ne sont pas suivis : un lien vers `/` ferait parcourir
    tout le conteneur, et `copy2` le recopie tel quel de toute façon.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            yield Path(dirpath) / name


def measure(root: Path) -> tuple[int, int]:
    """(nombre de fichiers, octets). Les deux compteurs de la barre de progression.

    Comptés avant la copie et non au fil de l'eau : une barre dont le total
    bouge pendant qu'elle avance ne dit plus rien. Un fichier disparu entre la
    mesure et la copie est ignoré ici — `restore` s'en accommode.
    """
    files = 0
    total = 0
    for file in iter_files(root):
        try:
            total += file.stat().st_size
        except OSError:
            continue
        files += 1
    return files, total


# --- écriture -----------------------------------------------------------


def _unique(target: Path) -> Path:
    """Un nom libre à côté de `target`, pour ne jamais écraser."""
    for index in range(1, 1000):
        candidate = target.with_name(f"{target.name}.mount-guard-{index}")
        if not candidate.exists():
            return candidate
    raise OSError(f"Aucun nom libre à côté de {target}")


def _merge_move(src: Path, dst: Path) -> int:
    """Déplace `src` sur `dst`, en fusionnant les répertoires. Rend le nombre de
    collisions résolues par renommage.

    La fusion n'est pas de la coquetterie : une mise de côté interrompue laisse
    un `_local` à moitié peuplé, et la reprise repasse dessus. Sans fusion, le
    second passage renommerait tout un arbre parce que son répertoire racine
    existe déjà.
    """
    if not dst.exists():
        os.rename(src, dst)
        return 0
    if src.is_dir() and dst.is_dir():
        conflicts = 0
        for child in sorted(src.iterdir()):
            conflicts += _merge_move(child, dst / child.name)
        try:
            src.rmdir()
        except OSError:
            # Il reste quelque chose dedans — un fichier créé entre-temps par
            # l'add-on. On le laisse : il sera repris au passage suivant.
            _LOGGER.debug("%s non vide après fusion, laissé en place", src)
        return conflicts
    # Collision entre deux fichiers, ou entre un fichier et un répertoire. On ne
    # détruit rien : le nouveau venu se range à côté sous un nom dérivé.
    alt = _unique(dst)
    _LOGGER.warning("Collision sur %s : rangé sous %s", dst, alt.name)
    os.rename(src, alt)
    return 1


@dataclass(frozen=True, slots=True)
class StashResult:
    moved: int
    conflicts: int


def stash(path: Path) -> StashResult:
    """Étape 2 : déplace le **contenu** de `path/` vers `path_local/`.

    Le contenu, jamais le répertoire : le point de montage est un bind mount, et
    le renommer lève `EBUSY`. C'est le piège qui fait écrire cette étape à
    l'envers la première fois.

    Idempotente : relancée après une coupure, elle reprend ce qui reste. C'est
    ce qui permet à la reprise au démarrage de ne pas avoir à savoir où la
    précédente s'était arrêtée.
    """
    stashed = stash_dir(path)
    stashed.mkdir(parents=True, exist_ok=True)
    moved = 0
    conflicts = 0
    for child in sorted(path.iterdir()):
        conflicts += _merge_move(child, stashed / child.name)
        moved += 1
    _LOGGER.info("Mise de côté de %s vers %s : %d entrées", path, stashed, moved)
    return StashResult(moved=moved, conflicts=conflicts)


def rollback(path: Path) -> StashResult:
    """Remet le contenu de `path_local/` dans `path/`, et supprime `path_local`.

    Appelée quand le rechargement a échoué : le montage n'est pas là, donc
    `path` est toujours le dossier local, et l'add-on doit y retrouver ses
    fichiers avant de repartir. Ne rien faire laisserait l'add-on redémarrer sur
    un répertoire vide, ce qui ressemble à une perte de données même quand tout
    est encore là, à côté.
    """
    stashed = stash_dir(path)
    if not stashed.exists():
        return StashResult(moved=0, conflicts=0)
    moved = 0
    conflicts = 0
    for child in sorted(stashed.iterdir()):
        conflicts += _merge_move(child, path / child.name)
        moved += 1
    try:
        stashed.rmdir()
    except OSError as err:
        _LOGGER.warning("%s non supprimé (%s)", stashed, err)
    return StashResult(moved=moved, conflicts=conflicts)


@dataclass(frozen=True, slots=True)
class RestoreResult:
    copied: int
    skipped: int
    bytes_done: int
    cancelled: bool
    errors: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """Tout est passé : la source peut être supprimée."""
        return not self.cancelled and not self.errors


ProgressCallback = Callable[[int, int, str], None]


def _stat_or_none(path: Path) -> os.stat_result | None:
    """`stat`, ou None si le fichier n'est pas là.

    Un seul aller-retour, là où `exists()` puis `stat()` en font deux. Sur un
    partage réseau, la différence n'est pas cosmétique : c'est la moitié du
    coût de la vérification, répétée par fichier.
    """
    try:
        return path.stat()
    except OSError:
        return None


def _should_copy(
    source: os.stat_result, target: os.stat_result | None, overwrite: str
) -> bool:
    """Le fichier local doit-il remplacer celui qui est déjà sur le NAS ?

    La politique est réglée **par montage** et non globalement : un partage
    d'enregistrements de caméra, dont l'add-on est le seul écrivain, et un
    partage de documents que plusieurs appareils modifient n'ont pas la même
    réponse. Un réglage unique obligerait à choisir la prudence pour tout le
    monde, donc à laisser Frigate perdre les siens.

    Reçoit des `stat_result` déjà obtenus, et ne touche pas au disque : sur
    83 000 fichiers, un `stat` de plus par fichier coûte des minutes.

    Un fichier absent côté NAS est toujours copié, quelle que soit la politique :
    aucune des trois ne dit « jeter ».
    """
    if target is None:
        return True
    if overwrite == OVERWRITE_ALWAYS:
        return True
    if overwrite == OVERWRITE_NEVER:
        return False
    # keep_newest, et tout réglage inconnu : le plus prudent des trois, celui
    # qui ne perd rien. Un réglage illisible — configuration écrite à la main,
    # option retirée d'une version future — ne doit pas se traduire par un
    # écrasement.
    return source.st_mtime > target.st_mtime


def _copy_one(source: Path, target: Path, source_stat: os.stat_result) -> None:
    """Copie un fichier en préservant sa date, et rien d'autre.

    `copyfile` + `os.utime` plutôt que `copy2`, qui appelle en plus `chmod` et
    la copie des attributs étendus — deux à trois allers-retours de plus par
    fichier sur un partage réseau.

    Ce qu'on perd est sans objet ici : les permissions d'un fichier sur un
    partage CIFS sont **imposées par les options de montage** (`uid`, `gid`,
    `file_mode`), et un `chmod` y est au mieux ignoré. Ce qu'on garde est ce
    dont tout dépend : la date de modification, sur laquelle repose la
    politique `keep_newest` et le classement des enregistrements.
    """
    shutil.copyfile(source, target)
    os.utime(target, (source_stat.st_atime, source_stat.st_mtime))


def restore(
    path: Path,
    *,
    overwrite: str = DEFAULT_OVERWRITE,
    concurrency: int = DEFAULT_CONCURRENCY,
    on_progress: ProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> RestoreResult:
    """Étape 4 : rapatrie `path_local/` dans `path/`, maintenant monté.

    Trois règles de sûreté, chacune payée par un scénario de perte :

    - **la politique d'écrasement est réglée par montage** (`overwrite`), et son
      défaut ne perd rien : le fichier le plus récent gagne. Pendant la panne,
      un autre appareil a pu écrire sur le partage, et sa version est alors la
      bonne. Un montage dont l'add-on est le seul écrivain se règle en
      `always` ; un partage où le NAS fait autorité, en `never`.
    - **l'annulation n'est consultée qu'entre deux fichiers.** Interrompre une
      copie laisse un fichier tronqué sur le NAS, indiscernable d'un fichier
      valide. `cancel` est un service que l'utilisateur déclenche ; il ne doit
      pas pouvoir corrompre quoi que ce soit.
    - **`path_local` n'est supprimé qu'à la fin, et seulement si tout est
      passé.** Voir l'en-tête du module.

    **Le coût réel est la latence, pas le débit.** Un partage CIFS répond en
    quelques millisecondes, et un rapatriement de dizaines de milliers de
    vignettes passe l'essentiel de son temps à attendre des allers-retours
    plutôt qu'à transférer des octets. Trois choses en découlent, et ce sont
    elles qui font la vitesse de cette fonction :

    1. **un `mkdir` par répertoire, pas par fichier** — `seen_dirs` ;
    2. **un seul `stat` de la destination** (`_stat_or_none`) au lieu d'un
       `exists()` suivi d'un `stat()` ;
    3. **`copyfile` + `utime`** au lieu de `copy2` — voir `_copy_one`.

    `concurrency` attaque la latence de front : les copies sont réparties sur
    un petit groupe de threads, qui attendent le réseau en parallèle. C'est le
    seul levier qui change l'ordre de grandeur sur un corpus de petits
    fichiers. `1` rétablit le parcours strictement séquentiel.
    """
    stashed = stash_dir(path)
    if not stashed.exists():
        return RestoreResult(0, 0, 0, cancelled=False, errors=())

    state = _RestoreState(
        path=path,
        stashed=stashed,
        overwrite=overwrite,
        on_progress=on_progress,
        should_cancel=should_cancel,
    )

    if concurrency <= 1:
        for source in iter_files(stashed):
            if state.stop_requested():
                break
            state.handle(source)
    else:
        state.run_concurrently(concurrency)

    result = state.result()
    if result.complete:
        shutil.rmtree(stashed, ignore_errors=True)
        _LOGGER.info(
            "Rapatriement de %s terminé : %d copiés, %d déjà à jour côté NAS",
            path,
            result.copied,
            result.skipped,
        )
    else:
        _LOGGER.warning(
            "Rapatriement de %s incomplet (%s) : %s conservé",
            path,
            "annulé" if result.cancelled else f"{len(result.errors)} erreurs",
            stashed,
        )
    return result


class _RestoreState:
    """L'état partagé d'un rapatriement, séquentiel ou concurrent.

    Une classe et non des variables locales : avec plusieurs threads, les
    compteurs doivent être protégés, et les avoir tous au même endroit est ce
    qui garantit qu'aucun n'a été oublié.

    Deux verrous distincts, et c'est délibéré. `_lock` ne protège que des
    incréments — aucune E/S dessous, sinon il sérialiserait exactement ce qu'on
    cherche à paralléliser. `_dirs_lock`, lui, couvre bien un `mkdir` : voir
    `_ensure_dir`.
    """

    def __init__(
        self,
        *,
        path: Path,
        stashed: Path,
        overwrite: str,
        on_progress: ProgressCallback | None,
        should_cancel: Callable[[], bool] | None,
    ) -> None:
        self.path = path
        self.stashed = stashed
        self.overwrite = overwrite
        self.on_progress = on_progress
        self.should_cancel = should_cancel

        self._lock = threading.Lock()
        self._dirs_lock = threading.Lock()
        self._seen_dirs: set[Path] = set()
        self.copied = 0
        self.skipped = 0
        self.bytes_done = 0
        self.errors: list[str] = []
        self.cancelled = False

    def stop_requested(self) -> bool:
        if self.should_cancel is not None and self.should_cancel():
            self.cancelled = True
            return True
        return False

    def _ensure_dir(self, parent: Path) -> None:
        """Un `mkdir` par répertoire, pas par fichier.

        C'est l'économie la plus rentable de la fonction : Frigate range ses
        enregistrements par caméra et par heure, donc quelques centaines de
        répertoires pour des dizaines de milliers de fichiers.
        """
        with self._dirs_lock:
            if parent in self._seen_dirs:
                return
            # Le `mkdir` se fait SOUS le verrou, et c'est la seule E/S de ce
            # module qui s'y trouve. Marquer le répertoire comme vu avant de
            # l'avoir créé laisse un second thread copier dedans pendant que le
            # premier attend encore le réseau : `FileNotFoundError` sur la
            # destination, de façon intermittente et seulement en concurrence.
            # C'est exactement ce qu'a montré
            # `test_a_cancelled_run_resumes_and_finishes`.
            #
            # Le coût est négligeable : une fois par répertoire, pas par
            # fichier. Et si le `mkdir` échoue, le répertoire n'est pas
            # mémorisé, donc le fichier suivant réessaiera.
            parent.mkdir(parents=True, exist_ok=True)
            self._seen_dirs.add(parent)

    def handle(self, source: Path) -> None:
        relative = source.relative_to(self.stashed)
        target = self.path / relative
        try:
            source_stat = source.stat()
            self._ensure_dir(target.parent)
            if _should_copy(source_stat, _stat_or_none(target), self.overwrite):
                _copy_one(source, target, source_stat)
                copied = True
            else:
                copied = False
        except OSError as err:
            # On continue : un fichier illisible ne doit pas empêcher les
            # milliers d'autres de rentrer. `complete` restera faux, donc la
            # source sera conservée et la prochaine tentative reprendra
            # celui-là.
            _LOGGER.warning("Rapatriement de %s impossible : %s", relative, err)
            with self._lock:
                self.errors.append(f"{relative} : {err}")
            return

        with self._lock:
            if copied:
                self.copied += 1
            else:
                self.skipped += 1
            self.bytes_done += source_stat.st_size
            done = self.copied + self.skipped
            total = self.bytes_done
        if self.on_progress is not None:
            self.on_progress(done, total, str(relative))

    def run_concurrently(self, concurrency: int) -> None:
        """Répartit les copies sur un petit groupe de threads.

        Le nombre de tâches en vol est **borné** : soumettre les 83 000 fichiers
        d'un coup construirait autant d'objets `Future` avant d'en exécuter un
        seul, et rendrait l'annulation aussi lente que le rapatriement.

        L'annulation reste consultée **avant chaque soumission**, donc toujours
        entre deux fichiers : aucune copie n'est interrompue en cours.
        """
        pending: set[Future] = set()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for source in iter_files(self.stashed):
                if self.stop_requested():
                    break
                pending.add(pool.submit(self.handle, source))
                if len(pending) >= concurrency * 2:
                    _done, pending = wait(pending, return_when=FIRST_COMPLETED)
            wait(pending)

    def result(self) -> RestoreResult:
        return RestoreResult(
            self.copied,
            self.skipped,
            self.bytes_done,
            cancelled=self.cancelled,
            errors=tuple(self.errors),
        )
