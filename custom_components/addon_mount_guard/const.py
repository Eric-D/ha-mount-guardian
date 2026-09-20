"""Constantes de l'intégration Add-on Mount Guard."""

DOMAIN = "addon_mount_guard"

# --- options globales de l'entrée ---------------------------------------

CONF_SCAN_INTERVAL = "scan_interval"
CONF_RETRY_INTERVAL = "retry_interval"
CONF_MIN_FREE_RATIO = "min_free_ratio"
CONF_NOTIFY = "notify"

# 60 secondes. Le Supervisor pousse déjà `supervisor_event` quand un montage
# tombe ou se rétablit : ce polling n'est qu'un filet, pour le cas — le nôtre —
# où le montage est annoncé `active` alors que le bind mount a disparu du
# conteneur core. Descendre plus bas ne rendrait pas la détection plus rapide,
# l'événement arrivant en premier ; monter plus haut allongerait d'autant la
# fenêtre pendant laquelle l'add-on écrit en local sans que personne ne le sache.
DEFAULT_SCAN_INTERVAL = 60  # secondes
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 3600

# 120 secondes entre deux tentatives sur un montage qui a échoué. Un NAS qui
# redémarre répond au TCP avant d'avoir fini d'exporter ses partages : réessayer
# toutes les dix secondes arrêterait et relancerait les add-ons en boucle.
DEFAULT_RETRY_INTERVAL = 120  # secondes
MIN_RETRY_INTERVAL = 30
MAX_RETRY_INTERVAL = 3600

# 10 % d'espace libre sur le système de fichiers local. En dessous, les add-ons
# du montage sont arrêtés : un Frigate qui remplit la carte SD de
# l'installation emporte Home Assistant avec lui, et le repli en local n'a de
# sens que tant qu'il reste de la place pour ce repli.
DEFAULT_MIN_FREE_RATIO = 0.10
MIN_MIN_FREE_RATIO = 0.0  # 0 désactive le garde-fou
MAX_MIN_FREE_RATIO = 0.5

DEFAULT_NOTIFY = True

# --- données d'une sous-entrée (un add-on surveillé) --------------------

CONF_SLUG = "slug"
CONF_MOUNTS = "mounts"
CONF_MOUNT = "mount"
CONF_HOST = "host"
CONF_MODE = "mode"
CONF_OVERWRITE = "overwrite"

# Politique de rapatriement, réglable PAR MONTAGE : un partage de photos et un
# partage d'enregistrements de caméra ne se valent pas. Trois valeurs, et le
# défaut est celui qui ne perd rien :
#
# - `keep_newest` : le fichier le plus récent gagne. Pendant la panne, un autre
#   appareil a pu écrire sur le NAS ; sa version est la bonne, la nôtre a été
#   écrite en aveugle par un add-on qui croyait parler au partage.
# - `always` : le local écrase toujours. Pour un montage dont l'add-on est le
#   seul écrivain — le cas de Frigate — où la version locale est par
#   construction la plus à jour, même si l'horloge dit autre chose.
# - `never` : un fichier déjà présent côté NAS n'est jamais touché. Pour un
#   partage où le NAS fait autorité et où le repli local n'est qu'un tampon.
OVERWRITE_KEEP_NEWEST = "keep_newest"
OVERWRITE_ALWAYS = "always"
OVERWRITE_NEVER = "never"
OVERWRITE_MODES = (OVERWRITE_KEEP_NEWEST, OVERWRITE_ALWAYS, OVERWRITE_NEVER)
DEFAULT_OVERWRITE = OVERWRITE_KEEP_NEWEST

SUBENTRY_TYPE_ADDON = "addon"

# --- Supervisor ---------------------------------------------------------

# Les seuls usages de montage acceptés. `backup` est exclu délibérément : il n'a
# pas de <nom> dans son chemin — c'est `/backup` tout court — donc la mise de
# côté écrirait `/backup_local` à la racine du conteneur, et aucun add-on
# n'écrit en continu dans les sauvegardes. Le flux de configuration le refuse
# avec un message explicite plutôt que de l'accepter sans l'avoir testé.
SUPPORTED_USAGES = ("media", "share")

# Racine par usage, telle que le conteneur core la voit. Dérivée ici et non lue
# du Supervisor : ce qui compte est le chemin visible depuis Home Assistant, et
# c'est justement là que le bind mount peut manquer alors que le Supervisor
# annonce le montage actif.
USAGE_ROOTS = {"media": "/media", "share": "/share"}

# Suffixe du répertoire de mise de côté. Frère du point de montage, donc sur le
# même système de fichiers : les déplacements sont des renommages, pas des
# copies. Sa seule présence est l'état persistant de l'intégration — il n'y a
# pas de Store, cf. CLAUDE.md.
STASH_SUFFIX = "_local"

# Ports de test de joignabilité, par type de montage. Pas de ping ICMP : le
# conteneur core n'a pas toujours CAP_NET_RAW, et un repli silencieux sur le TCP
# rendrait le comportement dépendant de l'installation.
PROBE_PORTS = {"cifs": 445, "nfs": 2049}
DEFAULT_PROBE_PORT = 445
PROBE_TIMEOUT = 3.0  # secondes

# Délai d'attente de la confirmation du rechargement dans /proc/mounts.
RELOAD_TIMEOUT = 30.0  # secondes

# Délai d'attente de l'arrêt effectif d'un add-on. Le Supervisor rend la main
# avant que le conteneur ne soit réellement arrêté ; mettre de côté les fichiers
# pendant que l'add-on écrit encore est exactement ce que l'étape 1 existe pour
# empêcher. Soixante secondes parce qu'un Frigate qui vide ses tampons vidéo
# prend son temps.
STOP_TIMEOUT = 60.0  # secondes

# Cadence des sondages d'attente (état d'un add-on, présence du montage).
POLL_INTERVAL = 1.0  # secondes

# Coalescence de la progression. L'attribut d'entité est écrit au plus une fois
# par tranche : sans ça, mille fichiers copiés font mille écritures d'état, donc
# mille lignes de recorder et autant de rendus de la carte. Les changements
# d'état et d'étape, eux, sont publiés immédiatement — ils sont rares et c'est
# ce que l'utilisateur regarde.
PROGRESS_INTERVAL = 2.0  # secondes

# Trois échecs consécutifs sur un même montage ouvrent une réparation Home
# Assistant. Moins ferait remonter une panne transitoire du NAS ; plus ferait
# attendre une heure avant que l'utilisateur soit prévenu que l'automatique ne
# s'en sort pas.
FAILURES_BEFORE_ISSUE = 3

# --- bus et services ----------------------------------------------------

EVENT_MOUNT_GUARD = f"{DOMAIN}_event"

SERVICE_REPAIR = "repair"
SERVICE_SET_MODE = "set_mode"
SERVICE_CANCEL = "cancel"
