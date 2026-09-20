"""La séquence de réparation d'un montage.

C'est le seul endroit du dépôt qui arrête des add-ons et déplace des fichiers.
Tout y est injecté — l'API Supervisor, l'executor, l'horloge, la sieste, la
publication — pour que la séquence entière puisse être jouée sur un répertoire
temporaire, sans Home Assistant, sans Supervisor et sans attendre.

    1. stopping   arrêter les add-ons, et attendre qu'ils le soient vraiment
    2. stashing   déplacer <chemin>/* vers <chemin>_local/     (local_fallback)
    3. reloading  recharger le montage, attendre /proc/mounts
    4. restoring  rapatrier <chemin>_local/ dans <chemin>/     (local_fallback)
       rolling_back si le montage n'est pas revenu : tout remettre en place
    5. starting   relancer ce qui a le droit de repartir

**Deux règles de concurrence, et elles ne sont pas décoratives.**

Les verrous sont pris **par add-on**, dans l'ordre alphabétique des slugs, avant
la première étape. Deux montages sans add-on commun se réparent en parallèle ;
deux montages qui partagent Frigate se réparent l'un après l'autre. L'ordre fixe
est ce qui empêche l'interblocage quand deux montages partagent partiellement
leurs add-ons — un interblocage qui ne se verrait qu'en production, et seulement
parfois.

Le rappel de progression de `fileops.restore` s'exécute **dans le thread de
l'executor**. Il ne touche donc à rien d'asynchrone : il écrit dans un objet
ordinaire, qu'une tâche à part publie à cadence fixe. Appeler `publish` depuis
ce thread écrirait un état Home Assistant hors de la boucle d'événements, ce qui
marche à peu près, jusqu'au jour où ça ne marche plus.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable, MutableMapping
from contextlib import AsyncExitStack
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from . import fileops, machine
from .const import (
    DEFAULT_RETRY_INTERVAL,
    POLL_INTERVAL,
    PROGRESS_INTERVAL,
    RELOAD_TIMEOUT,
    STOP_TIMEOUT,
)
from .models import Remediation, RemediationAddon
from .mount_table import MountConfig, MountTable
from .supervisor_api import SupervisorApi, SupervisorApiError

_LOGGER = logging.getLogger(__name__)

CANCELLED = "Réparation annulée à la demande de l'utilisateur"


@dataclass
class RepairContext:
    """Ce que la séquence doit savoir du reste du monde.

    `states` est une fonction et non un dictionnaire : une séquence dure
    plusieurs minutes, pendant lesquelles d'autres montages changent d'état. La
    garde de relance de l'étape 5 doit interroger la situation **au moment où
    elle relance**, pas celle d'il y a trois minutes.
    """

    table: MountTable
    states: Callable[[], dict[str, Remediation]]
    #: Tenu par le coordinator et persisté : la remédiation de `nas_config` ne
    #: sait pas que c'est celle de `nas_media` qui a arrêté Frigate, et un
    #: redémarrage de Home Assistant ne doit pas faire oublier qui relancer.
    we_stopped: MutableMapping[str, bool]


@dataclass
class _Progress:
    """Miroir écrit depuis le thread de l'executor, lu depuis la boucle.

    Des entiers et une chaîne, rien d'autre : l'affectation d'un attribut est
    atomique en Python, donc aucun verrou n'est nécessaire, et la tâche de
    publication peut lire un lot légèrement incohérent sans conséquence — elle
    publie une barre de progression, pas une transaction.
    """

    files_done: int = 0
    bytes_done: int = 0
    current_file: str | None = None
    dirty: bool = False


@dataclass
class RepairRunner:
    """Exécute les séquences. Une instance par entrée de configuration."""

    api: SupervisorApi
    #: `hass.async_add_executor_job` en production.
    run_executor: Callable[..., Any]
    #: Publie une remédiation : attribut d'entité, WebSocket, événement.
    publish: Callable[[Remediation], None]
    #: `dt_util.utcnow` en production. Injectée pour que les tests ne dorment
    #: pas et que ruff (règle DTZ) n'ait aucune horloge naïve à signaler.
    now: Callable[[], datetime]
    retry_interval: int = DEFAULT_RETRY_INTERVAL
    sleep: Callable[[float], Any] = asyncio.sleep
    stop_timeout: float = STOP_TIMEOUT
    reload_timeout: float = RELOAD_TIMEOUT
    poll_interval: float = POLL_INTERVAL
    progress_interval: float = PROGRESS_INTERVAL

    #: Dernière remédiation publiée, par montage. Sert au rattrapage d'erreur :
    #: quand une exception traverse la séquence, `async_run` n'a plus sous la
    #: main que la remédiation d'avant — sans `started_at`, sans l'entrée de
    #: journal du passage en `repairing`, sans l'état des add-ons relevé à
    #: l'étape 1. Repartir de là effacerait tout ce que l'utilisateur vient de
    #: voir défiler sur la carte.
    _latest: dict[str, Remediation] = field(default_factory=dict, init=False)
    _locks: dict[str, asyncio.Lock] = field(default_factory=dict, init=False)
    _cancelled: set[str] = field(default_factory=set, init=False)
    _running: set[str] = field(default_factory=set, init=False)

    # --- pilotage externe ------------------------------------------------

    def request_cancel(self, mount: str) -> None:
        """Demande l'abandon. Prend effet entre deux étapes, ou entre deux
        fichiers pendant le rapatriement — jamais au milieu d'une copie."""
        if mount in self._running:
            _LOGGER.info("Abandon demandé pour %s", mount)
            self._cancelled.add(mount)

    def is_running(self, mount: str) -> bool:
        return mount in self._running

    def _should_cancel(self, mount: str) -> bool:
        return mount in self._cancelled

    def _lock(self, slug: str) -> asyncio.Lock:
        return self._locks.setdefault(slug, asyncio.Lock())

    # --- arrêt, utilisable hors séquence ---------------------------------

    async def async_stop_addons(
        self, config: MountConfig, remediation: Remediation, context: RepairContext
    ) -> Remediation:
        """Arrête les add-ons du montage et attend qu'ils le soient.

        Appelée par la séquence, mais aussi par deux chemins qui n'en font pas
        partie : le mode `stop_only` au moment de la panne, et le garde-fou
        d'espace disque. D'où sa présence en méthode publique plutôt que dans
        le corps de `async_run`.

        Idempotente : un add-on déjà arrêté — parce qu'une autre remédiation
        vient de le faire — n'est pas touché, et `we_stopped` garde la mémoire
        du premier arrêt. C'est ce qui permet à deux montages du même add-on de
        s'enchaîner sans qu'il ne redémarre entre les deux.
        """
        for slug in config.slugs:
            info = await self.api.addon_info(slug)
            if info.running:
                # Noté AVANT l'arrêt : si le Supervisor échoue à mi-chemin,
                # l'add-on peut être arrêté quand même, et l'oublier le
                # laisserait éteint pour de bon.
                context.we_stopped[slug] = True
                _LOGGER.info("Arrêt de %s (montage %s)", slug, config.mount)
                await self.api.stop_addon(slug)
            else:
                # `setdefault` et non une affectation : un add-on déjà arrêté
                # par la remédiation d'un montage voisin doit rester marqué
                # comme « arrêté par nous », sinon personne ne le relancerait.
                context.we_stopped.setdefault(slug, False)

        remediation = await self._await_addons_stopped(config, remediation)
        return remediation

    async def _await_addons_stopped(
        self, config: MountConfig, remediation: Remediation
    ) -> Remediation:
        """Le Supervisor rend la main avant que le conteneur ne soit arrêté.

        Mettre de côté les fichiers pendant que l'add-on écrit encore est
        exactement ce que l'étape 1 existe pour empêcher. On sonde donc jusqu'à
        constater l'arrêt, et le dépassement du délai est une erreur de la
        séquence, pas un détail qu'on ignore.
        """
        deadline = self.stop_timeout
        while True:
            infos = [await self.api.addon_info(slug) for slug in config.slugs]
            remediation = self._with_addons(remediation, infos)
            self._emit(remediation)
            if not any(info.running for info in infos):
                return remediation
            if deadline <= 0:
                still = ", ".join(i.slug for i in infos if i.running)
                raise SupervisorApiError(f"Add-ons toujours en marche après arrêt : {still}")
            await self.sleep(self.poll_interval)
            deadline -= self.poll_interval

    def _with_addons(self, remediation: Remediation, infos: list[Any]) -> Remediation:
        return replace(
            remediation,
            addons=tuple(
                RemediationAddon(
                    slug=info.slug,
                    name=info.name,
                    state="started" if info.running else "stopped",
                )
                for info in infos
            ),
            updated_at=self.now().isoformat(),
        )

    # --- la séquence -----------------------------------------------------

    async def async_run(
        self, config: MountConfig, remediation: Remediation, context: RepairContext
    ) -> Remediation:
        """Joue la séquence complète et rend la remédiation finale.

        Ne lève pas : toute panne est traduite en `degraded` avec son message et
        un réessai programmé. Une exception qui remonterait ici ferait échouer
        le cycle du coordinator, donc tous les autres montages avec celui-ci.
        """
        mount = config.mount
        if mount in self._running:
            _LOGGER.debug("Réparation de %s déjà en cours", mount)
            return remediation

        self._running.add(mount)
        self._cancelled.discard(mount)
        try:
            async with AsyncExitStack() as stack:
                # Ordre alphabétique garanti par MountConfig.slugs. Voir
                # l'en-tête du module : c'est ce qui évite l'interblocage.
                for slug in config.slugs:
                    await stack.enter_async_context(self._lock(slug))
                return await self._sequence(config, remediation, context)
        except (SupervisorApiError, OSError) as err:
            return self._fail(config, self._latest.get(mount, remediation), str(err))
        except Exception as err:  # volontairement large : voir la docstring
            _LOGGER.exception("Réparation de %s : erreur inattendue", mount)
            return self._fail(config, self._latest.get(mount, remediation), str(err))
        finally:
            self._running.discard(mount)
            self._cancelled.discard(mount)
            self._latest.pop(mount, None)

    async def _sequence(
        self, config: MountConfig, remediation: Remediation, context: RepairContext
    ) -> Remediation:
        path = Path(config.path)
        local = config.mode == "local_fallback"

        remediation = machine.start_repair(remediation, now=self.now())
        self._emit(remediation)

        # 1. stopping — toujours, y compris à la reprise après un redémarrage
        # de Home Assistant : le Supervisor a relancé les add-ons au passage, et
        # rapatrier des fichiers pendant que Frigate écrit dedans annulerait
        # tout le bénéfice de l'opération.
        remediation = self._step(remediation, "stopping")
        remediation = await self.async_stop_addons(config, remediation, context)

        if self._should_cancel(config.mount):
            return self._cancel(config, remediation, path, local)

        # Le montage est-il DÉJÀ actif ? C'est le cas de la reprise après un
        # redémarrage de Home Assistant, qui remonte les partages au passage.
        already_mounted = bool(await self.run_executor(fileops.is_mounted, path))

        # 2. stashing — seulement en local_fallback, et **jamais sur un montage
        # actif** : ce qu'on verrait sous le point de montage serait le contenu
        # du NAS, et on le déplacerait dans `<chemin>_local`. Le partage serait
        # vidé, l'opération réussirait, et rien ne le signalerait. C'est la
        # pire panne que ce module puisse produire.
        # Idempotente sinon : une reprise ramasse ce que la tentative
        # précédente avait laissé.
        if local and not already_mounted:
            remediation = self._step(remediation, "stashing")
            await self.run_executor(fileops.stash, path)
            if self._should_cancel(config.mount):
                return self._cancel(config, remediation, path, local)

        # 3. reloading — sauté lui aussi si le montage est déjà là : recharger
        # un partage en bon état, c'est le démonter puis le remonter, donc
        # prendre le risque d'une panne pour confirmer une bonne nouvelle.
        if already_mounted:
            mounted = True
        else:
            remediation = self._step(remediation, "reloading")
            await self.api.reload_mount(config.mount)
            mounted = await self._await_mounted(path)

        if not mounted:
            # 4b. rolling_back — le montage n'est pas revenu. On remet tout en
            # place plutôt que de laisser l'add-on redémarrer sur un répertoire
            # vide, ce qui ressemble à une perte de données même quand tout est
            # encore là, à côté.
            if local:
                remediation = self._step(remediation, "rolling_back")
                await self.run_executor(fileops.rollback, path)
            remediation = self._step(remediation, "starting")
            remediation = await self._start_allowed(config, remediation, context)
            return self._fail(
                config,
                remediation,
                f"Montage {config.mount} toujours absent {self.reload_timeout:.0f}s "
                "après le rechargement",
            )

        # 4a. restoring
        if local:
            remediation = self._step(remediation, "restoring")
            remediation = await self._restore(config, remediation, path)
            if self._should_cancel(config.mount):
                # Le montage est là et une partie des fichiers est passée :
                # `_local` est conservé par `fileops.restore`, la reprise
                # finira. On relance les add-ons pour ne pas les laisser
                # éteints sur un abandon volontaire.
                remediation = self._step(remediation, "starting")
                remediation = await self._start_allowed(config, remediation, context)
                return self._fail(config, remediation, CANCELLED)

        # 5. starting
        remediation = self._step(remediation, "starting")
        remediation = await self._start_allowed(config, remediation, context)

        remediation = machine.succeed(remediation, now=self.now())
        self._emit(remediation)
        _LOGGER.info("Montage %s réparé", config.mount)
        return remediation

    # --- étapes -----------------------------------------------------------

    async def _await_mounted(self, path: Path) -> bool:
        """Attend que /proc/mounts confirme, et non que le Supervisor réponde.

        Le Supervisor rend la main dès qu'il a lancé le montage ; ce qui compte
        est le moment où le conteneur core le voit. Rapatrier avant, c'est
        réécrire les fichiers dans le dossier local qu'on vient de vider.
        """
        deadline = self.reload_timeout
        while deadline > 0:
            if await self.run_executor(fileops.is_mounted, path):
                return True
            await self.sleep(self.poll_interval)
            deadline -= self.poll_interval
        return bool(await self.run_executor(fileops.is_mounted, path))

    async def _restore(
        self, config: MountConfig, remediation: Remediation, path: Path
    ) -> Remediation:
        """Rapatrie, en publiant la progression à cadence fixe."""
        files_total, bytes_total = await self.run_executor(
            fileops.measure, fileops.stash_dir(path)
        )
        remediation = replace(
            remediation,
            files_total=files_total,
            bytes_total=bytes_total,
            files_done=0,
            bytes_done=0,
            updated_at=self.now().isoformat(),
        )
        self._emit(remediation)

        progress = _Progress()

        def on_progress(files_done: int, bytes_done: int, current: str) -> None:
            # Thread de l'executor. On n'écrit que des attributs.
            progress.files_done = files_done
            progress.bytes_done = bytes_done
            progress.current_file = current
            progress.dirty = True

        holder: dict[str, Remediation] = {"value": remediation}

        async def ticker() -> None:
            while True:
                await self.sleep(self.progress_interval)
                if not progress.dirty:
                    continue
                progress.dirty = False
                holder["value"] = replace(
                    holder["value"],
                    files_done=progress.files_done,
                    bytes_done=progress.bytes_done,
                    current_file=progress.current_file,
                    updated_at=self.now().isoformat(),
                )
                self._emit(holder["value"])

        pump = asyncio.ensure_future(ticker())
        try:
            # `functools.partial` et non des positionnels : `restore` n'accepte
            # ses options qu'en nommé, et `async_add_executor_job` ne transmet
            # que du positionnel. Les intervertir se verrait tout de suite ;
            # oublier `overwrite` ne se verrait pas — la politique par défaut
            # s'appliquerait à tous les montages, en silence.
            result = await self.run_executor(
                functools.partial(
                    fileops.restore,
                    path,
                    overwrite=config.overwrite,
                    on_progress=on_progress,
                    should_cancel=lambda: self._should_cancel(config.mount),
                )
            )
        finally:
            pump.cancel()

        remediation = replace(
            holder["value"],
            files_done=result.copied + result.skipped,
            bytes_done=result.bytes_done,
            current_file=None,
            updated_at=self.now().isoformat(),
        )
        if result.errors:
            _LOGGER.warning(
                "Rapatriement de %s : %d fichiers en échec", config.mount, len(result.errors)
            )
        self._emit(remediation)
        return remediation

    async def _start_allowed(
        self, config: MountConfig, remediation: Remediation, context: RepairContext
    ) -> Remediation:
        """Étape 5 : relance ce qui a le droit de repartir.

        La liste est décidée par `machine.plan_restart`, interrogée **ici** et
        pas plus tôt : la situation des autres montages a pu changer pendant les
        minutes qu'a duré le rapatriement.
        """
        plan = machine.plan_restart(
            config.mount, context.table, context.states(), dict(context.we_stopped)
        )
        for slug in plan.start:
            _LOGGER.info("Relance de %s (montage %s)", slug, config.mount)
            await self.api.start_addon(slug)
            context.we_stopped[slug] = False
        for slug in plan.held:
            _LOGGER.info(
                "%s maintenu arrêté : un autre de ses montages attend sa réparation", slug
            )

        states = {slug: "started" for slug in plan.start}
        states.update({slug: "held" for slug in plan.held})
        remediation = replace(
            remediation,
            addons=tuple(
                replace(addon, state=states.get(addon.slug, addon.state))
                for addon in remediation.addons
            ),
            updated_at=self.now().isoformat(),
        )
        self._emit(remediation)
        return remediation

    # --- abandon et échec --------------------------------------------------

    def _cancel(
        self, config: MountConfig, remediation: Remediation, path: Path, local: bool
    ) -> Remediation:
        """Abandon entre deux étapes, avant le rechargement.

        Les fichiers mis de côté sont remis en place : le montage n'est pas
        revenu, donc `<chemin>` est toujours le dossier local, et l'add-on doit
        y retrouver ses enregistrements avant de repartir.
        """
        if local:
            # Synchrone volontairement : on est sur un chemin d'abandon, et un
            # rollback est une suite de renommages sur le même système de
            # fichiers — quelques millisecondes.
            fileops.rollback(path)
        return self._fail(config, remediation, CANCELLED)

    def _fail(self, config: MountConfig, remediation: Remediation, error: str) -> Remediation:
        """Retour au repli local, réessai programmé.

        **Y compris après un abandon volontaire**, et c'est délibéré :
        l'utilisateur a annulé *cette tentative*, pas la surveillance. Ne rien
        reprogrammer laisserait le montage dégradé pour toujours ; reprogrammer
        immédiatement ignorerait son geste. Le délai de réessai ordinaire est le
        seul compromis qui ne boucle pas — et le service `repair` court-circuite
        l'attente pour qui veut relancer tout de suite.
        """
        remediation = machine.fail(
            remediation, now=self.now(), error=error, retry_interval=self.retry_interval
        )
        self._emit(remediation)
        _LOGGER.warning("Réparation de %s en échec : %s", config.mount, error)
        return remediation

    # --- publication -------------------------------------------------------

    def _step(self, remediation: Remediation, step: str) -> Remediation:
        remediation = machine.enter_step(remediation, step, now=self.now())
        self._emit(remediation)
        return remediation

    def _emit(self, remediation: Remediation) -> None:
        """Publie tout de suite.

        Il n'y a pas de drapeau de coalescence ici : la seule chose assez
        bavarde pour en mériter une est la progression du rapatriement, et elle
        est déjà regroupée par la tâche `ticker`, qui ne publie qu'une fois par
        `progress_interval`. Un paramètre toujours vrai finirait par être lu de
        travers.
        """
        self._latest[remediation.mount] = remediation
        self.publish(remediation)
