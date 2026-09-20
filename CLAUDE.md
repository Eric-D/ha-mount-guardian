# Notes pour les contributeurs (humains et agents)

Ce dépôt reprend le cycle de vie, l'architecture et l'outillage de
[ha-escalade-veauche](https://github.com/Eric-D/ha-escalade-veauche). Les
invariants repris ci-dessous y ont été payés cher ; ils sont réécrits ici avec
leur ancre dans **ce** code, parce qu'un renvoi vers un autre dépôt n'est pas
lu.

**La différence structurante : cette intégration agit.** Là-bas, le pire défaut
affichait un mauvais horaire. Ici, une erreur arrête un add-on, déplace des
gigaoctets, et peut faire disparaître des enregistrements. Tout ce qui décide
est donc pur, isolé et testé, et tout ce qui touche au disque refuse plutôt que
d'improviser.

Ce qui n'a pas d'équivalent ici n'est pas repris : il n'y a **pas de scraper**,
**pas de cache disque de données**, **pas de créneaux**, et **pas
d'authentification** — le Superviseur répond au conteneur core sans identifiant,
et le NAS n'est joint que par une socket TCP ouverte puis refermée.
`tests/test_init.py::TestNoAuthenticationPath` empêche qu'un
`ConfigEntryAuthFailed` y revienne par copier-coller.

---

## Ce qui commande toute l'architecture : le harnais de test

`tests/conftest.py` fabrique un MagicMock pour tout import de `homeassistant.*`,
`voluptuous` et `aiohasupervisor`. Deux conséquences, et la seconde est un
piège :

- **deux bases mockées** lèvent `TypeError: metaclass conflict`. C'est le cas de
  `class _Base(CoordinatorEntity, SensorEntity)` dans `sensor.py` : le module
  n'est pas importable, et tout ce qui y vit est hors de portée de la suite.
- **une seule base mockée ne lève pas.** Elle produit une « classe » qui *est*
  un MagicMock : elle s'importe, s'instancie, et toutes ses méthodes sont
  muettes. Aucune erreur, CI verte, code jamais exécuté.

D'où l'invariant le plus important du dépôt :

> **Aucun module testable ne dérive de `DataUpdateCoordinator`.**
> Le coordinator est **instancié** dans `async_setup_entry` (`__init__.py`) — un
> appel, pas un héritage — et reçoit `MountGuardDataSource.async_update`.

`tests/test_init.py::TestTheCoordinatorIsBuiltNotInherited` passe au peigne tous
les `.py` du composant pour le vérifier, et
`tests/test_coordinator.py::TestNothingInherits` vérifie que la source est une
vraie classe. Sans eux, écrire `class MountGuardCoordinator(DataUpdateCoordinator)`
ferait passer trente tests au vert sans rien exécuter.

### Où vit la logique testable

Non importables sous les mocks, donc **sans aucune logique** :

| Module | Pourquoi |
|---|---|
| `sensor.py`, `binary_sensor.py`, `button.py` | deux bases mockées |
| `config_flow.py` | dérive de `ConfigFlow` — une base, donc muet et vert |
| `websocket_api.py` | `@websocket_api.websocket_command` remplace la fonction décorée |

Tout le reste porte la logique et **doit rester importable** :
`const`, `models`, `mount_table`, `machine`, `supervisor_api`, `reachability`,
`fileops`, `repair`, `coordinator`, `entities`, et `__init__` lui-même.
`tests/test_imports.py::TestTestableModulesStayImportable` est le cliquet : le
jour où l'un d'eux importerait `SensorEntity`, **tous** ses tests
disparaîtraient de la collecte sans qu'aucun ne devienne rouge.

`tests/test_entities.py::TestThePlatformsStayThin` complète le dispositif : une
plateforme qui se mettrait à importer `machine`, `fileops` ou `repair` signale
qu'une décision vient d'échapper aux tests.

---

## La machine à états : `degraded` et `pending` ne se confondent pas

```
ok ──(montage perdu)──► degraded ──(NAS joignable)──► pending
 ▲                         ▲   │                        │
 │                         │   └──(NAS reparti)─────────┘
 │                    (échec, réessai)                   │
 └─────────(succès)────────┴────────────────────── repairing
```

C'est la distinction dont dépend **toute la gestion des add-ons partagés**
(`machine.plan_restart`) :

- **`degraded`** : le NAS ne répond pas. L'add-on écrit en local et **c'est le
  comportement voulu**. Il n'y a rien à faire qu'attendre.
- **`pending`** : le NAS a répondu. La réparation est due mais n'a pas commencé
  — un autre montage partageant les mêmes add-ons tient le verrou, ou un
  réessai est programmé.

### La règle de relance, et celle qu'on inverse en croyant bien faire

À l'étape 5, un add-on n'est relancé que si **aucun autre de ses montages n'a
besoin d'une remédiation**, c'est-à-dire n'est ni `pending` ni `repairing`
(`models.needs_remediation`).

**Un montage `degraded` ne retient personne.** Le retenir laisserait l'add-on
arrêté aussi longtemps que le second NAS resterait éteint, et viderait le mode
`local_fallback` de son sens. `tests/test_machine.py::TestPlanRestart::
test_a_degraded_sibling_does_not_hold_the_addon` verrouille exactement ça.

**Le regroupement tombe tout seul de cette règle**, et il n'y a pas de mécanisme
de lot : deux montages du même add-on qui reviennent ensemble donnent **un**
arrêt et **une** relance. Le premier ne relance pas (le second est `pending`),
le second trouve l'add-on déjà arrêté et le relance en sortant.
(`TestTheBatchingFallsOutOfTheRule`.)

Deux compléments nécessaires :

- **Verrous par add-on, dans l'ordre alphabétique des slugs** (`repair.py`,
  `async_run`, via `MountConfig.slugs` déjà trié). L'ordre fixe évite
  l'interblocage quand deux montages partagent partiellement leurs add-ons — un
  interblocage qui ne se verrait qu'en production, et seulement parfois.
- **On ne relance que ce qu'on a arrêté.** `we_stopped` est tenu par le
  coordinator, pas par la remédiation : celle de `nas_config` ne sait pas que
  c'est celle de `nas_media` qui a arrêté Frigate. Il est persisté, sans quoi un
  redémarrage ferait oublier qui relancer.

### `step_index` et `step_count` sont dérivés, jamais donnés

`Remediation.__post_init__` les recale sur `step` et `mode` à chaque
construction **et à chaque `replace`**. Les laisser libres les laisse mentir : un
`replace(mode=...)` dessinerait cinq cases pour une séquence qui en fait trois,
un `replace(step=...)` laisserait le stepper allumé sur l'étape précédente. Les
deux sont invisibles au typage, aux tests de forme et à la relecture. C'est aussi
ce qui rend `dataclasses.replace` sûr partout ailleurs.

### `stop_only` garde `reloading`

Trois étapes, pas deux. **Le Superviseur ne recharge pas un montage tombé** —
c'est la raison d'être de cette intégration. Sans cette étape, un montage en
`stop_only` ne reviendrait jamais et ses add-ons resteraient arrêtés
indéfiniment. Ce que ce mode retire, c'est le déplacement de fichiers.

---

## Ce qui peut détruire des données

### On ne met JAMAIS de côté un montage actif

`repair.py` relève `already_mounted` avant l'étape 2 et saute **la mise de côté
et le rechargement** quand le montage est déjà là.

Sans cette garde : Home Assistant redémarre, le Superviseur remonte le partage,
la reprise démarre, et l'étape 2 déplace ce qu'elle voit sous le point de
montage — **le contenu du NAS** — vers `<chemin>_local`. Le partage vidé, la
séquence réussie, rien pour le signaler. C'est la pire panne que ce dépôt puisse
produire. (`tests/test_repair.py::TestAnActiveMountIsNeverStashed`.)

Le rechargement est sauté pour une raison distincte : recharger un partage en bon
état, c'est le démonter puis le remonter — prendre le risque d'une panne pour
confirmer une bonne nouvelle.

### `<chemin>_local` est un **frère**, pas un enfant

`fileops.stash_dir`. Le bind mount recouvre le point de montage, pas son voisin :
un `_local` placé dessous disparaîtrait au rechargement de l'étape 3, avec tout
ce qu'on venait d'y mettre. Frère aussi parce qu'il est alors sur le même
système de fichiers : les déplacements sont des renommages instantanés.

### On déplace le contenu, jamais le répertoire

Le point de montage est un bind mount : `os.rename` dessus lève `EBUSY`. C'est le
piège qui fait écrire l'étape 2 à l'envers la première fois.

### Trois règles de `fileops`, chacune payée par un scénario de perte

- **Aucune collision ne détruit quoi que ce soit.** Un fichier en trop se range
  à côté sous un nom dérivé (`_unique`) ; un fichier écrasé ne revient pas.
- **La source n'est supprimée qu'après un parcours complet et sans erreur**
  (`RestoreResult.complete`). Une reprise recopie ce qui est déjà passé — c'est
  gratuit grâce à la comparaison des dates — alors qu'une source supprimée au
  fil de l'eau laisse, après une coupure, la moitié des fichiers nulle part.
- **L'annulation n'est consultée qu'entre deux fichiers.** Interrompre un
  `copy2` laisse un fichier tronqué sur le NAS, indiscernable d'un fichier
  valide. `cancel` est un service que l'utilisateur déclenche ; il ne doit pas
  pouvoir corrompre quoi que ce soit.

### Le coût d'un rapatriement est la LATENCE, pas le débit

Mesuré sur une installation réelle : **une dizaine de fichiers par seconde** en
séquentiel, soit plus de deux heures pour 83 000 vignettes de Frigate — alors
que le débit ne dépassait pas 200 ko/s. Un partage CIFS répond en quelques
millisecondes, et chaque fichier coûtait cinq à six allers-retours.

Quatre décisions de `fileops.restore` en découlent, et aucune n'est
cosmétique :

1. **un `mkdir` par répertoire, pas par fichier** (`_RestoreState._ensure_dir`).
   Frigate range par caméra et par heure : quelques centaines de répertoires
   pour des dizaines de milliers de fichiers ;
2. **un seul `stat` de la destination** (`_stat_or_none`), là où `exists()`
   puis `stat()` en faisaient deux ;
3. **`copyfile` + `os.utime`** au lieu de `copy2` (`_copy_one`). Ce qu'on perd
   est sans objet : les permissions d'un fichier sur un partage CIFS sont
   **imposées par les options de montage** (`uid`, `gid`, `file_mode`), et un
   `chmod` y est au mieux ignoré. Ce qu'on garde est ce dont tout dépend — la
   date de modification, sur laquelle reposent `keep_newest` et le classement
   des enregistrements ;
4. **`concurrency`, réglable par montage** (8 par défaut). C'est le seul levier
   qui change l'ordre de grandeur : huit threads attendent le réseau huit fois
   plus efficacement.

Deux conséquences à ne pas défaire :

- **`_ensure_dir` fait son `mkdir` SOUS le verrou.** Marquer le répertoire
  comme vu avant de l'avoir créé laisse un second thread copier dedans pendant
  que le premier attend encore le réseau : `FileNotFoundError` sur la
  destination, de façon intermittente et seulement en concurrence. C'est un
  vrai bug, attrapé par `test_a_cancelled_run_resumes_and_finishes`.
- **L'ordre de la progression n'est plus déterministe** au-delà de
  `concurrency=1`. Le parcours (`iter_files`) reste trié, mais l'ordre
  d'achèvement ne l'est pas, et `current_file` désigne l'un des fichiers en
  vol. Les **compteurs**, eux, restent monotones : ils sont incrémentés sous
  `_lock`, et `test_the_progress_counters_never_go_backwards` le vérifie — une
  barre qui recule est le symptôme le plus visible d'un état partagé mal
  protégé.

`_lock` ne couvre que des incréments : y mettre une E/S sérialiserait
exactement ce qu'on cherche à paralléliser.

### La politique d'écrasement est réglée **par montage**

`overwrite` : `keep_newest` (défaut), `always`, `never`. Un partage
d'enregistrements dont l'add-on est le seul écrivain et un partage de documents
que plusieurs appareils modifient n'ont pas la même réponse ; un réglage unique
obligerait à choisir la prudence pour tout le monde, donc à laisser Frigate
perdre les siens.

Deux subtilités testées : **aucune des trois politiques ne jette un fichier
absent du NAS** (`never` protège ce qui existe, il ne refuse pas les nouveaux
venus), et **un réglage illisible retombe sur `keep_newest`** — une option
retirée d'une version future ne doit pas se traduire par un écrasement.

`keep_newest` dépend de la préservation des dates par `copy2` : une copie qui ne
les préserverait pas daterait tous les fichiers de l'instant du rapatriement, et
le rapatriement suivant les croirait tous récents.

### Le cas qu'on ne sait pas rattraper

`machine.ERROR_MASKED_LOCAL_FILES`. Si le montage se rétablit **sans passer par
la séquence** — redémarrage de Home Assistant pendant que le NAS est revenu —
les fichiers écrits en local passent sous le bind mount et deviennent
inaccessibles depuis le conteneur core. On ne peut pas démonter : aucun accès à
l'hôte, et `POST /mounts/{name}/reload` remonte aussitôt.

`DELETE /mounts/{name}` suivi d'un `POST /mounts` ouvrirait la fenêtre, mais
perdrait la configuration de stockage de l'utilisateur si la recréation échouait.
**Décision prise : on ne touche pas.** On détecte, on le dit dans `last_error` et
dans le journal du montage, et c'est écrit dans les limites du README.

---

## Persistance : deux mémoires, et les deux sont nécessaires

> Le `Store` retient **l'intention** — quel montage était dégradé, quels add-ons
> nous avions arrêtés, ce que dit le journal. Le système de fichiers retient
> **les fichiers**, par la seule présence de `<chemin>_local`. Chaque cycle
> réconcilie les deux.

Un fichier d'état peut mentir sur ce que contient le disque ; le disque ne dit
pas qui relancer. C'est ce qui fait de la **reprise après redémarrage un cas
ordinaire** plutôt qu'un chemin à part : `machine.observe` reçoit `stashed`, et
la présence de `<chemin>_local` force une remédiation, montage revenu ou non —
avec le délai de réessai qui s'applique toujours.

Deux règles qui en découlent :

- **Un `repairing` persisté revient en `pending` au chargement**
  (`MountGuardDataSource.async_load`). La séquence qui le tenait n'existe plus,
  et `repairing` empêcherait `observe` de le regarder : il resterait figé pour
  toujours, ses add-ons arrêtés avec lui.
- **Toute reprise commence par arrêter les add-ons.** Au redémarrage de Home
  Assistant, le Superviseur les a relancés ; rapatrier pendant que Frigate écrit
  dedans annulerait tout le bénéfice de l'opération.

`models.from_wire` **ramène chaque champ dans son vocabulaire** plutôt que de le
recopier : un `state` inconnu relu sans filtre se propagerait jusqu'à
`needs_remediation`, qui répondrait non, et l'add-on repartirait au milieu d'une
remédiation.

---

## Le contrat de remédiation

Défini **une seule fois** dans `models.py`, miroir TypeScript dans
`frontend/src/types.ts`, croisement dans `tests/test_models.py` — clés de chaque
interface **et** littéraux de chaque union. Deux langages, deux outillages, deux
CI : rien d'autre ne les relie, et un état ajouté d'un côté se rendrait en
pastille grise sans libellé de l'autre.

**Un seul chemin de publication**, `MountGuardDataSource.publish`, et un seul
sérialiseur, `models.to_wire`. Les trois canaux — attribut d'entité, WebSocket,
événement `addon_mount_guard_event` — servent le même dictionnaire. Trois chemins
qui composeraient leur propre payload, c'est trois occasions d'en laisser un
derrière au premier champ ajouté, sans que rien ne devienne rouge.

Un événement n'est émis que sur **changement d'état** : la progression d'un
rapatriement publie une douzaine de fois en deux minutes, et un événement par
publication noierait les automatisations.

Le seul renommage à la frontière : `from_` → `from`, mot-clé Python et pas
mot-clé JavaScript. Il est porté par la métadonnée du champ, pas par un cas
particulier dans `to_wire` — la seule forme qui reste juste quand un deuxième
champ s'y ajoute.

---

## Ce qui ne doit jamais bloquer la boucle d'événements

Trois choses que Python sait faire en bloquant sans rien dire, et qui gèleraient
Home Assistant entier — interface comprise — pendant toute leur durée :

| | Où | Comment |
|---|---|---|
| Ouvrir une socket vers le NAS | `reachability.py` | `asyncio.open_connection`, jamais `socket.connect` |
| Lire `/proc/mounts` | `fileops.is_mounted` | appelé via `run_executor` |
| Copier des gigaoctets | `fileops.restore` | idem |

`fileops` est **volontairement synchrone**. Une fonction `async` qui appelle
`shutil.copy2` ment sur ce qu'elle fait, et personne ne se demande plus où elle
tourne. Ici la signature dit « je bloque », et `repair.py` reçoit un
`run_executor` par lequel tout passe.

**Le rappel de progression s'exécute dans le thread de l'executor.** Il n'écrit
que des attributs d'un objet ordinaire (`_Progress`) ; une tâche `ticker` les
publie toutes les deux secondes depuis la boucle. Publier un état Home Assistant
depuis un thread de travail « marche à peu près », jusqu'au jour où ça ne marche
plus.

La règle `ASYNC` de ruff verrouille le premier point. Une exemption existe,
`ASYNC109` sur `reachability.async_is_reachable` : la règle veut que le délai
vienne de l'appelant, mais ici **le délai est la sémantique** — un NAS qui met
huit secondes à accepter une connexion n'est pas joignable au sens de cette
intégration — et le remonter obligerait les trois appelants à se souvenir de le
poser.

**Pas de ping ICMP.** Le conteneur core n'a pas toujours `CAP_NET_RAW`, et un
repli silencieux vers le TCP rendrait le comportement dépendant de
l'installation : la même configuration se comporterait différemment chez deux
utilisateurs. Une connexion TCP sur le port du partage est de toute façon un
meilleur test — c'est ce port précis que le montage va utiliser.

---

## Le Superviseur

**Un seul point d'entrée**, `supervisor_api.py`, par-dessus
`homeassistant.components.hassio.get_supervisor_client` — exporté dans le
`__all__` du composant, et typé. **Ne pas revenir à
`hass.data["hassio"].send_command`** : c'est l'ancien client non typé, et il
faudrait réécrire à la main le déballage de l'enveloppe et la carte des URL.

`aiohasupervisor` **n'est pas dans `requirements`**, et la formulation exacte
compte : c'est une dépendance du **composant `hassio`**, pas du paquet
`homeassistant`. Elle figurait encore dans les `requires_dist` du cœur en
2026.1.0 et en est sortie depuis — le job `import-check (dernière)` l'a
découvert au premier passage. Home Assistant l'installe au moment de mettre
`hassio` en place, et notre `dependencies: ["hassio"]` garantit que cela
précède l'import de nos modules. L'y déclarer de notre côté imposerait une borne
qui entrerait en conflit avec celle que `hassio` épingle, et pip refuserait
d'installer l'intégration. C'est pourquoi le job `import-check` lit les
exigences du composant dans son manifeste plutôt que de les épingler.

Il est mocké dans `conftest.py`, avec une **vraie** classe d'exception — un
MagicMock dans une clause `except` lève « catching classes that do not inherit
from BaseException », et tout le module deviendrait intestable en silence.

Trois choses que la lecture des modèles amont a apprises, et qu'il faut
continuer à vérifier :

- **`AddonState` a cinq valeurs, dont `startup`.** Un add-on en `startup` n'est
  **pas** arrêté. L'oublier ferait croire l'étape 1 terminée alors que Frigate
  ouvre justement ses fichiers, et la mise de côté partirait sous ses pieds.
  D'où `ADDON_RUNNING_STATES = ("started", "startup")`.
- **`MountState` a sept valeurs**, dont `activating` et `reloading` — des états
  transitoires qu'il ne faut confondre ni avec `active` ni avec `failed`.
- **`user_path` est absent tant que le montage n'a jamais été activé**, donc
  précisément quand on en a le plus besoin. Il est gardé pour recouper notre
  propre dérivation (`mount_table.mount_path`), jamais comme source unique.

Côté droits, vérifié dans `supervisor/api/middleware/security.py` : le jeton du
cœur est reconnu **avant** toute vérification de rôle. Une intégration custom a
donc l'accès complet au Superviseur. Ce qu'elle n'a pas : `mount` / `umount`
(pas de `CAP_SYS_ADMIN`, pas de namespace hôte) — c'est ce qui rend le cas des
fichiers masqués irrattrapable.

`async_handle_supervisor_event` **ne fait confiance à rien du contenu** : il
déclenche un relevé, qui ira lire `/proc/mounts`. C'est la seule source qui dise
ce que voit le conteneur core, et toute cette intégration existe parce que le
Superviseur et lui divergent. `os.path.ismount()` ne suffit pas : il compare le
numéro de périphérique du répertoire à celui de son parent, ce qui répond faux
pour un bind mount issu du même système de fichiers — exactement notre cas.

---

## Le mode et l'hôte appartiennent au **montage**

`entry.options["mounts"][<nom>] = {host, mode, usage, overwrite}` ; la
sous-entrée d'un add-on ne contient que `{slug, mounts: [<noms>]}`.

Un montage est un objet physique unique : il ne peut pas être réparé de deux
façons parce que deux add-ons l'ont déclaré différemment, ni pointer vers deux
NAS. **Le conflit n'est pas arbitré, il est rendu impossible par la forme du
stockage.** Le formulaire de sous-entrée demande quand même ces réglages, mais
les pré-remplit à partir du premier montage connu — en proposer d'autres
donnerait l'illusion qu'on peut les faire diverger.

`mount_table.build_mount_table` tolère trois incohérences plutôt que de lever,
parce que toutes arrivent pendant l'édition et qu'une exception empêcherait
l'entrée de se charger : montage inconnu des options, montage déclaré deux fois
par un add-on, et **montage qu'aucun add-on n'utilise**. Ce dernier est écarté
de la surveillance, et c'est délibéré : la séquence déplace des fichiers, elle
existe pour arbitrer entre un add-on qui écrit et un montage disparu sous lui ;
sans add-on, remuer `/media/x` serait une initiative que rien n'a demandée.

`/backup` est refusé dès le flux de configuration : il n'a pas de `<nom>` dans
son chemin, donc la mise de côté écrirait `/backup_local` à la racine du
conteneur.

---

## Comment la carte est chargée — ne pas revenir en arrière

**La carte est déclarée comme ressource Lovelace, et uniquement comme ça.**
`add_extra_js_url()` ne doit être appelé qu'en dernier recours, quand la
collection de ressources est indisponible (mode YAML).

### Pourquoi

Home Assistant charge `@webcomponents/scoped-custom-element-registry`. Ce
polyfill **remplace** `window.customElements` :

```js
Object.defineProperty(window, 'customElements', {
  value: new CustomElementRegistry(), configurable: true, writable: true });
...
get(tagName) { return this._definitionsByTag.get(tagName)?.elementClass; }
```

Son `get()` ne consulte que sa propre table. `nativeGet` est capturé au démarrage
mais **jamais interrogé**. Toute définition faite avant son installation lui est
donc invisible, définitivement.

`add_extra_js_url()` injecte le script dans le document : il peut être évalué
*avant* le polyfill. La définition atterrit alors dans le registre natif, Home
Assistant appelle `customElements.get()` → rien → « Custom element doesn't
exist », et son rattrapage par `whenDefined()` est mort-né pour la même raison.

Les ressources Lovelace sont chargées par le panneau (`ha-panel-lovelace`), donc
toujours **après** le polyfill. C'est exactement pourquoi les cartes distribuées
en ressource (auto-entities, card-mod, mushroom…) ne rencontrent jamais ce
problème.

### Symptôme caractéristique

```
customElements.get('mount-guard-card')               → undefined
document.createElement('mount-guard-card').setConfig  → "function"
```

Les deux ne peuvent diverger que s'il existe deux registres.

### Contre-intuitif

C'est le chargement le **plus rapide** qui échoue : le polyfill s'installe aux
alentours de 110–130 ms, et arriver avant lui est précisément ce qui casse.

### Ce que dit la documentation

La page officielle sur les cartes personnalisées ne décrit **que** le mécanisme
des ressources de tableau de bord, et ne mentionne ni `add_extra_js_url` ni
`extra_module_url` :
https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/

---

## Invariants de la carte

### Écarts délibérés au contrat des cartes personnalisées

Ces trois-là ressemblent à des oublis. Ne pas les « corriger ».

- **`setConfig()` ne lève pas pour une entité absente ou vide** (`card.ts`). La
  convention Home Assistant veut qu'elle lève ; ça rendait la carte
  irrécupérable depuis l'interface, remplacée définitivement par « Erreur de
  configuration » et sans la moindre trace console. `ha-form` émet
  `entity: undefined` quand on vide le champ ; l'éditeur le recoerce en `''`
  (`editor.ts`, `_valueChanged`) et `setConfig` tolère en second rempart. **Les
  deux sont nécessaires** : retirer l'un en croyant l'autre suffisant restaure
  la panne. Seule une configuration non-objet lève encore.
- **Pas de garde d'égalité dans le setter `hass`.** Un early-return sauterait
  `_syncEntityState()` et laisserait l'état vide au premier rendu. Elle serait
  de surcroît sans effet, `requestUpdate()` filtrant déjà par `notEqual`. Le
  filtrage des re-rendus vit dans `shouldUpdate()`, qui doit conserver un cas
  non évident : `_config` doit toujours passer, car il peut arriver dans le même
  lot qu'un `hass` dont les états n'ont pas bougé.
- **Pas de `performUpdate()` synchrone dans `connectedCallback`.** Il y en a eu
  un sur le dépôt d'origine, ajouté contre une cause inventée ; il faisait rendre
  la carte de façon ré-entrante dans le commit Lit de Home Assistant.

### Ce qui doit rester vrai

- **Aucune dépendance externe dans le bundle** (`frontend/package.json` : que des
  `devDependencies`). Pas de CDN, pas de police distante — la carte doit
  fonctionner en WebView Android et sur une installation sans accès Internet.
  `tests/test_manifest.py::TestCardIsShipped` le vérifie sur le bundle commité.
- **Jamais `unsafeHTML` ni `unsafeSVG`.** Il n'y en a aucun, et il ne doit pas y
  en avoir : `last_error` vient du backend, donc potentiellement d'un message
  d'erreur système. Deux tests le vérifient par le rendu réel
  (`chrome.test.ts`, `history.test.ts`).
- **`render()` retourne toujours un `<ha-card>` visible**, loader compris. Pas
  parce que Home Assistant inspecterait le shadow root — il ne le fait pas —
  mais parce qu'un rendu vide ne distingue pas une carte qui charge d'une carte
  cassée.
- **Le dernier rendu n'est conservé que tant qu'il reste des retries**, sur les
  **trois** chemins d'indisponibilité de `_render` (`!states`, entité absente,
  entité `unavailable`). Au-delà, message explicite : afficher indéfiniment une
  remédiation périmée ferait croire à une réparation en cours alors que Home
  Assistant ne répond plus. Le budget vaut environ 100 s
  (`helpers/retry.ts` : dix essais, `2000 × n` plafonné à 15 000), remis à zéro
  à chaque reconnexion de l'élément.
- **`customElements.define` reste gardé** par `if (!customElements.get(...))`
  (fin de module de `card.ts`, deux fois, et de `editor.ts`) : sur WebView
  Android le script peut être ré-évalué au retour de veille.
- **`window.customCards.push`** : nécessaire au sélecteur de cartes. Rien en CI
  ne détecterait sa suppression.
- **L'événement `mount-guard-card-update`** est émis après chaque rendu effectif
  (`card.ts`, `updated`). Contrat public pour les greffons tiers — card-mod
  notamment — sans aucun consommateur dans ce dépôt.
- **Aucun timer lié à un élément ne survit à son détachement, ni la souscription
  WebSocket.** `disconnectedCallback` annule le retry, le `setInterval` d'une
  seconde et le `RemediationFeed` ; `connectedCallback` remet le quota à zéro.
  La portée est volontairement étroite : la fin de module installe sept
  `setTimeout` pour la réparation des cartes d'erreur orphelines, qui ne
  dépendent d'aucun élément — légitime, à usage unique et plafonnés à quatre
  secondes.

**Ne pas extraire le bloc d'enregistrement** de `card.ts` sans très bonne
raison : c'est le code le plus débogué du fichier, et aucun test frontend ne
rattraperait une erreur.

Les rendus purement présentatifs vivent dans `renders/` : ils ne touchent pas à
l'état de la carte et reçoivent leurs gestionnaires en paramètres. Leurs
signatures passent par un **objet nommé** (`renderMountRow({ remediation, now,
… })`). Deux chaînes adjacentes dans une signature positionnelle s'inversent sans
que le typage ni le linter ne disent rien, et le rendu reste parfaitement
lisible avec le mauvais texte.

### Le WebSocket est un raccourci, jamais une dépendance

`helpers/subscribe.ts` ne lève **jamais** : il signale. L'attribut de
`sensor.mount_guard_remediations` porte déjà tout le contrat ; la souscription
ne fait qu'éviter d'attendre le relevé suivant, jusqu'à une minute plus tard.
Une souscription qui lèverait dans `connectedCallback` laisserait la carte à
moitié montée, sans rendu et sans message.

Le bandeau « connexion temps réel perdue » n'apparaît que si la souscription a
**fonctionné puis a été perdue** (`feed.lost`). Sur une installation où le
WebSocket n'a jamais répondu, un bandeau permanent apprendrait à l'ignorer.

La fusion se fait **par `mount`, jamais par position** (`merge`) : l'attribut et
le flux n'ordonnent rien de la même façon, et une fusion positionnelle
écraserait la remédiation d'un montage avec celle d'un autre — silencieusement,
et seulement quand plusieurs montages sont en panne à la fois.

### La progression se calcule sur les octets, et le pourcentage est annoncé avec eux

`helpers/progress.ts`. Mille vignettes et un enregistrement d'une heure font
1001 fichiers, dont un seul pèse. Une barre en fichiers sauterait à 99 % en deux
secondes puis n'avancerait plus pendant dix minutes — le comportement qui fait
croire à un blocage. Repli sur les fichiers quand `bytes_total` vaut 0.

**Le pourcentage est donc affiché à côté des octets, pas du compteur de
fichiers.** Collé à ce dernier, il se lisait comme le leur : un premier
rapatriement réel affichait « 447 / 83136 fichiers (0 %) » alors que les
fichiers en étaient à 0,5 % — les deux ratios diffèrent d'un facteur cent sur
un corpus où quelques enregistrements pèsent l'essentiel.

### Le débit et le temps restant sont mesurés côté carte

`helpers/rate.ts`. Côté carte et non côté backend, parce que le backend n'a
rien à en dire de plus : il publierait le même calcul, au prix d'un champ de
plus dans le contrat et d'un miroir de plus à tenir d'accord.

La mesure part du **premier échantillon vu pour cette tentative**, jamais de
`started_at` : celui-ci couvre aussi l'arrêt des add-ons, la mise de côté et le
rechargement, qui ne transfèrent aucun octet. Sur une séquence où l'arrêt d'un
Frigate prend trente secondes, l'inclure annoncerait le double du temps réel
pendant les premières minutes.

Rien n'est annoncé tant que l'intervalle fait moins d'une seconde ou qu'aucun
octet n'a bougé : sur un intervalle plus court, le bruit d'échantillonnage fait
sauter l'estimation d'un facteur dix, et un temps restant qui saute est pire
que pas de temps restant du tout.

### Le temps passe côté carte, mais rien d'autre

`now` est **injecté** dans `renderMountRow` : c'est ce qui rend le temps écoulé
testable, et ce qui garantit que toutes les lignes d'un même rendu affichent le
même instant. Un `setInterval` d'une seconde le rafraîchit — à la minute, le
compte à rebours resterait figé sur « 01:47 » pendant soixante secondes.

C'est possible parce que **le backend n'envoie que des instants UTC**, jamais des
dates civiles : ils se soustraient à l'horloge du navigateur sans que le fuseau
configuré dans Home Assistant n'entre en jeu. Ne pas transposer ici la règle
inverse du dépôt d'origine, qui portait sur des délais en jours.

### Couleurs

**Uniquement des jetons de thème** : `--success-color`, `--warning-color`,
`--error-color`, `--primary-color`, `--primary-text-color`,
`--secondary-text-color`. Une couleur figée est illisible dans la moitié des
thèmes installés, et le défaut ne se voit que chez celui qui n'utilise pas le
même thème que l'auteur. Un test le vérifie sur la pastille d'état
(`mount-row.test.ts`).

**La pastille ne porte jamais de texte**, et le libellé l'accompagne toujours :
une pastille seule est illisible pour un daltonien, et le contraste ne distingue
pas trois états. C'est ce qui garantit le 4,5:1 sans avoir à calculer quoi que
ce soit — le texte reste sur les paires que Home Assistant garantit.

---

## Données d'exécution et rechargement

Le client, la source, le runner et le coordinator vivent dans
`entry.runtime_data` (`coordinator.MountGuardRuntimeData`), **pas** dans
`hass.data[DOMAIN][entry_id]`. Home Assistant le supprime lui-même au
déchargement réussi.

Deux filtres dans `guard_entries`, et **les deux sont nécessaires** :
`runtime_data` n'existe pas tant qu'`async_setup_entry` ne l'a pas posé (ça
écarte les entrées désactivées, ignorées et déchargées), et l'état, parce que
`runtime_data` est posé tôt et **survit à un setup qui échoue ensuite** — sans ce
filtre, une entrée en erreur retiendrait les services indéfiniment.

**Rien ne fait respecter l'affectation de `runtime_data`.** L'attribut n'a pas de
défaut et son absence est silencieuse — `guard_entries` l'écarte par un
`getattr`. Ne jamais le poser rendrait l'intégration entièrement muette, CI
verte. D'où `tests/test_init.py::TestRuntimeDataIsActuallyWired`, qui lit la
source.

`async_remove_entry` n'exclut pas l'entrée en cours de suppression : Home
Assistant la décharge avant d'appeler le handler, donc le filtre d'état s'en
charge. **Ne pas se fier à sa présence dans la collection** : HA a inversé
l'ordre en 2025.3.

**Un seul endroit recharge** : le listener `async_update_options`
(`__init__.py`). Il couvre aussi l'ajout, la modification et la suppression de
sous-entrée — la table inversée est reconstruite par `async_setup_entry`, donc
il n'y a **pas deux chemins de reconstruction** à garder d'accord.

Home Assistant déprécie `async_update_reload_and_abort` pour une intégration qui
enregistre un listener de mise à jour, avec une **casse annoncée en 2026.12**.
D'où `update_entry_and_ensure_reload` (`__init__.py`), qui programme le
rechargement lui-même dans les deux cas où **aucun listener n'est appelé** :
l'entrée n'a pas changé (`async_update_entry` renvoie `False` sans rien
notifier), ou aucun listener n'est enregistré. **Ne pas passer à
`OptionsFlowWithReload`** malgré son nom engageant : sa docstring l'interdit
quand un listener est enregistré.

Le helper vit dans `__init__.py` et non dans le flux, `config_flow.py` n'étant
pas importable sous les mocks.

`guard_entries` vit dans `coordinator.py` et est réexporté : le WebSocket en a
besoin, et `__init__.py` importe le WebSocket — le laisser là créait un cycle.

**Les services sont retirés au retrait de l'entrée, pas à son déchargement.** Un
rechargement passe par unload puis setup, et les retirer entre les deux
laisserait une fenêtre — le temps du setup des plateformes — pendant laquelle
une automatisation reçoit `ServiceNotFound`. Les rechargements sont fréquents.

### Identifiants uniques

Ils dérivent de l'`entry_id` et d'un nom **stable** — slug d'add-on ou nom de
montage — **jamais** d'une option. Un identifiant qui dépend d'un réglage
signifie qu'en changer crée des entités neuves et orpheline les anciennes :
tableau de bord cassé, historique perdu, automatisations muettes. Il n'y a pas de
module de migration ici, et c'est précisément pourquoi il faut que ça le reste.

Le préfixe `_addon_` / `_mount_` n'est pas cosmétique : rien n'interdit
d'appeler « frigate » à la fois l'add-on et le montage — c'est même le cas le
plus naturel — et sans lui les deux appareils fusionneraient.

---

## Traductions

`strings.json` n'est **jamais lu à l'exécution** pour une intégration
personnalisée : Home Assistant ne charge que `translations/<langue>.json`, avec
repli sur `en`. Une clé présente dans le seul `strings.json` s'affiche donc en
clé brute à l'utilisateur.

`en.json` n'est pas optionnel : `en` est la langue de **repli**, donc ce que voit
tout utilisateur non francophone.

`tests/test_translations.py` croise le flux, les sous-entrées, **les options des
sélecteurs** (un `translation_key` sans options fait choisir entre
« local_fallback » et « stop_only » écrits tels quels), **les noms d'entités** et
leurs placeholders, la réparation `repair_failed`, et `services.yaml` — champ par
champ, sur **tous** les fichiers. Ne pas le restreindre à `strings.json`.

---

## Méthode de diagnostic

Le chemin nominal de la carte est instrumenté à dessein (`setConfig accepté`,
`premier rendu effectué`, horodatages). **Ne pas retirer ces logs** : sans eux,
« aucun log » est ambigu entre « HA n'a jamais utilisé notre élément » et « tout
s'est bien passé », et c'est ce raisonnement faux qui a fait perdre le plus de
temps sur le dépôt d'origine.

Pour extraire la configuration réelle d'une carte d'erreur, depuis la console :

```js
(function w(n){if(!n)return;if(String(n.localName).startsWith('hui-error'))console.log('>>>',JSON.stringify(n._config??n.config));[...(n.shadowRoot?.children??[]),...(n.children??[])].forEach(w)})(document.body)
```

Pour voir passer les transitions : *Outils de développement → Événements*,
écouter `addon_mount_guard_event`, puis appeler `addon_mount_guard.repair`.

Pour savoir ce que voit réellement le conteneur core :
*Outils de développement → Modèles*, ou plus simplement le capteur binaire du
montage, dont les attributs portent la remédiation complète.

---

## Build

Le bundle `custom_components/addon_mount_guard/www/mount-guard-card.js` est
commité et la CI vérifie qu'il correspond aux sources. Après toute modification
de `frontend/src/`, lancer `cd frontend && npm run build` avant de commiter.

### Poser une version

Les versions vivent dans **six** fichiers : `manifest.json`, `CARD_VERSION` de
`__init__.py`, `frontend/src/version.ts`, `frontend/package.json`,
`frontend/package-lock.json`, et le bundle reconstruit.
`tests/test_manifest.py` vérifie qu'ils restent d'accord — désynchronisés, et
sur `CARD_VERSION` en particulier, ça ferait resservir un bundle périmé
derrière un cache-buster frais.

**L'ordre est : poser les versions dans un commit, puis taguer ce commit.** Le
workflow de release ne les recalcule pas, il les **vérifie**, et refuse de
publier si le manifeste et le tag ne disent pas la même chose.

> **Le workflow de release ne pousse rien sur `main`**, et c'est une correction
> payée cher. Sa version précédente, reprise du dépôt d'origine, recalculait
> les numéros à partir du tag puis committait le résultat sur `main`. Le jour
> où un tag existant a été repoussé — réécriture d'historique pour corriger
> l'identité des commits — le workflow s'est rejoué et a **ramené `main` à la
> version du tag**, écrasant celle d'après. Une vérification qui échoue coûte
> un tag à refaire ; un bump automatique qui part de travers coûte une branche.

Corollaire : **repousser un tag existant relance le workflow de release.** Sur
une réécriture d'historique, il faut s'y attendre et vérifier `main` ensuite.

---

## Publication

Trois contrôles HACS portent sur le **dépôt GitHub** et non sur le code, donc
rien en local ne les voit :

- **description** et **topics** du dépôt, réglés une fois via `gh repo edit` ;
- **images de marque**, soit dans
  `custom_components/addon_mount_guard/brand/`, soit par une entrée dans
  `home-assistant/brands`.

Le troisième est **désactivé** dans `validate.yml` (`ignore: brands`) le temps
de l'alpha. C'est le seul contrôle HACS neutralisé, et il doit être réactivé
avant la première version stable : sans images, la fiche du dépôt reste sans
visuel dans HACS.

Le workflow de release marque une **pré-version** dès que le tag porte un
suffixe (`-alpha`, `-beta`, `-rc`). HACS ne propose une pré-version qu'aux
utilisateurs ayant coché « afficher les versions bêta », ce qui permet de
publier sans la pousser à tout le monde.

---

## Linters

`ruff check .` — configuré dans `pyproject.toml`, exécuté en CI. Longueur de
ligne à 100 et non aux 88 de Home Assistant core, pour rester aligné sur le
dépôt d'origine.

`npm test` côté carte — le runner intégré de Node, sans vitest ni jest. Les
fonctions de `renders/` sont rendues dans un **vrai DOM** (`happy-dom`) puis
interrogées, plutôt qu'inspectées via les `strings` et `values` du
`TemplateResult` : un `@click` ne se distingue d'un autre qu'en le déclenchant.
C'est ce qui permet de voir ce que ni `tsc` ni oxlint ne voient — deux
paramètres de même type inversés, un gestionnaire branché sur le mauvais bouton.

**`helpers/` compte au moins autant que les rendus.** Une erreur dans `renders/`
se voit à l'œil au premier chargement ; « 1,2 Go » au lieu de « 1,2 Mo » est
parfaitement lisible.

Trois contraintes du harnais, dans `test/_setup.ts`, à ne pas défaire :

- le DOM est installé par `--import ./test/_setup.ts` et non par un import dans
  les fichiers de test : leurs imports statiques sont évalués avant leur corps,
  donc Lit se chargerait avant que `HTMLElement` existe ;
- `--conditions=browser` est nécessaire, sans quoi Node résout l'export « node »
  de Lit, qui suppose un rendu serveur et lève à l'import ;
- les globales de la famille `Event` viennent de happy-dom et **remplacent**
  celles de Node, qui refuse les siennes (« parameter 1 is not of type Event »).
  La règle porte sur toute la famille, pas sur une liste de noms.

Un crochet de résolution réécrit les imports `./x.js` des sources en `./x.ts`.
Le `.js` est une **convention du dépôt** — `moduleResolution` vaut `Bundler` —
mais le dépouillement de types de Node ne sait pas la suivre.

`card.ts` reste hors d'atteinte de ce runner : il utilise des décorateurs, que le
dépouillement de types de Node refuse. Ne pas y perdre de temps sans changer
d'outillage.

`npm run lint` côté TypeScript — **oxlint**, pas ESLint, qui a son propre parser
et aucune dépendance de pair sur TypeScript. Il tourne sur son ruleset
`correctness` par défaut, zéro constat. Ne pas élargir à `suspicious` ou
`pedantic` sans réfléchir : `no-underscore-dangle` y produit une trentaine de
faux positifs sur la convention `_private` des cartes Lovelace.

---

## Exécuter les tests

```
pip install -r requirements_test.txt
python scripts/manifest_requirements.py
pip install -r manifest-requirements.txt
pytest
ruff check .
(cd frontend && npm ci && npm run typecheck && npm run lint && npm test && npm run build)
git diff --exit-code --stat custom_components/addon_mount_guard/www/mount-guard-card.js
```

Ce bloc reproduit les vérifications de la CI, et `tests/test_documentation.py`
compare les deux pour qu'ils ne divergent pas — découvrir l'écart en poussant est
le genre de friction que ce dépôt s'efforce de supprimer partout ailleurs.

Le sous-shell est volontaire : sans lui, un build en échec laisserait le shell
dans `frontend/`, et la ligne suivante échouerait à son tour sur un chemin
introuvable, en masquant le vrai problème.

La dernière ligne est celle qu'on oublie le plus souvent : le bundle commité doit
correspondre au build, et la CI échoue sinon. `--exit-code --stat` plutôt que
`--quiet`, qui sort en 1 sans rien afficher.

Les deux commandes du milieu restent nécessaires **même sans dépendance
runtime** : `scripts/manifest_requirements.py` produit aujourd'hui un fichier
vide, et c'est ce qui fait qu'une dépendance ajoutée un jour au manifeste sera
prise en compte sans toucher aux workflows.

---

## Version minimale de Home Assistant

`2026.1.0`, déclarée dans `hacs.json`. **C'est une politique de support, plus
qu'une dérivation des API utilisées** : seule la série 2026 est prise en charge.

Ce qui reste vrai pour autant, et qu'il faut continuer à vérifier contre les
sources avant d'employer une API nouvelle :

- sous-entrées de configuration (`ConfigSubentryFlow`,
  `async_get_supported_subentry_types`) → **2025.2** ;
- `get_supervisor_client` du composant hassio → 2024.11 ;
- `async_register_static_paths` et `StaticPathConfig` → 2024.7 ;
- `getGridOptions()` de la carte → frontend `20241106.0`, soit 2024.11 ;
- `entry.runtime_data` et `ConfigEntry[T]` → 2024.6 ;
- `OptionsFlow.config_entry` → 2024.12.

`tests/test_manifest.py` n'est qu'un cliquet : il empêche d'abaisser le plancher,
il ne peut pas détecter qu'une API récente exige davantage.

### Versions de Python

Elles suivent le plancher, et elles divergent à dessein entre les jobs :

- `target-version` de ruff et le job `test-python` sur **3.13**, le
  `REQUIRED_PYTHON_VER` de 2026.1 ;
- `import-check` tourne deux fois, sur les deux extrémités de l'intervalle
  supporté : **3.13 avec `homeassistant==2026.1.0`**, le plancher lui-même, et
  **3.14 avec la dernière**, qui l'exige depuis 2026.3. Sans la première, le
  plancher ne serait qu'un nombre dans `hacs.json` que rien n'exécute. Sans la
  seconde, on ne verrait pas l'amont casser l'intégration.

**Développer sur 3.13 au minimum.** La suite passe sur des versions plus
anciennes — `conftest.py` simule Home Assistant — mais ce vert ne prouve rien
pour un utilisateur du plancher.

---

## Ce que l'amont peut casser

Par ordre de fragilité :

1. **`aiohasupervisor` et ses modèles.** Un champ renommé sur `MountResponse` ou
   `InstalledAddon` casse `supervisor_api.py` — et les tests, qui passent un
   double, ne le verraient pas. Le job `import-check` de la CI est le seul
   endroit qui le dirait, et il tourne aussi sur l'exécution programmée
   quotidienne. **Il a déjà servi** : au premier passage, il a montré que la
   bibliothèque avait quitté les dépendances du paquet `homeassistant` entre
   2026.1.0 et 2026.9.3.
2. **`get_supervisor_client`.** Exporté dans le `__all__` du composant hassio,
   mais ce n'est pas une garantie de stabilité. Sa disparition ne produirait
   aucune alerte ailleurs : `import-check` l'importe explicitement pour ça.
3. **La disposition des montages** (`/media/<nom>`, `/share/<nom>`). Dérivée par
   `mount_table.mount_path` et recoupée avec le `user_path` du Superviseur quand
   il est renseigné.
4. **`supervisor_event`.** Son format peut changer ; ce n'est qu'un accélérateur,
   le polling de 60 s reprend la main si l'événement cesse d'arriver.
