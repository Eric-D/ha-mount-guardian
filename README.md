# Add-on Mount Guard

Intégration Home Assistant qui remet d'aplomb les **stockages réseau** quand ils
tombent sous les pieds d'un add-on.

[![Validate](https://github.com/Eric-D/ha-mount-guardian/actions/workflows/validate.yml/badge.svg)](https://github.com/Eric-D/ha-mount-guardian/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

---

## Le problème

Sur Home Assistant OS, les stockages réseau (*Paramètres > Système > Stockage*)
sont montés par le Superviseur et exposés en `/media/<nom>` ou `/share/<nom>`.

Quand le NAS redémarre :

1. le montage passe en **`failed`**, et le Superviseur le retire ;
2. l'add-on continue d'écrire — dans le **dossier local** qui était sous le
   point de montage. Frigate enregistre, et remplit la carte SD ;
3. au retour du NAS, **le montage ne se recharge pas tout seul** ;
4. quand il se recharge, les fichiers écrits en local se retrouvent **recouverts**
   par le partage et deviennent inaccessibles.

Cette intégration ferme la boucle. Elle détecte la panne, **laisse l'add-on
tourner en local** — c'est un repli assumé, pas un accident —, puis quand le NAS
répond de nouveau :

```
1. arrête les add-ons concernés, et attend qu'ils soient vraiment arrêtés
2. met les fichiers locaux de côté, dans <chemin>_local
3. recharge le montage, et attend que /proc/mounts le confirme
4. rapatrie les fichiers sur le NAS, avec progression
5. relance les add-ons
```

Une carte Lovelace montre où en est chaque remédiation.

## Installation

### Via HACS

1. HACS → menu ⋮ → **Dépôts personnalisés**
2. URL `https://github.com/Eric-D/ha-mount-guardian`, catégorie **Integration**
3. Installer, puis **redémarrer Home Assistant**
4. *Paramètres > Appareils et services > Ajouter une intégration* → **Add-on Mount Guard**

La carte Lovelace est enregistrée automatiquement comme ressource : il n'y a
rien à ajouter à la main.

### Manuellement

Copier `custom_components/addon_mount_guard/` dans le dossier
`config/custom_components/` de Home Assistant, puis redémarrer.

## Configuration

### Réglages globaux

| Réglage | Défaut | Ce qu'il fait |
|---|---|---|
| Intervalle de relevé | 60 s | Filet sous les événements du Superviseur, pour le cas où il annonce un montage actif que Home Assistant ne voit pas. |
| Intervalle de réessai | 120 s | Attente après une réparation en échec. Un NAS qui redémarre répond au réseau avant d'avoir fini d'exporter ses partages. |
| Espace libre local minimum | 10 % | En dessous, les add-ons du montage sont arrêtés. `0` désactive ce garde-fou. |
| Notifications persistantes | activées | Panne, arrêt d'urgence. |

### Un add-on surveillé = une sous-entrée

*Add-on Mount Guard → **Ajouter un add-on surveillé***. Deux étapes :

1. **l'add-on**, choisi dans la liste que renvoie le Superviseur ;
2. **ses montages**, et pour chacun l'hôte du NAS, le comportement en panne et
   la politique de rapatriement.

> **Les réglages appartiennent au montage, pas à l'add-on.** Un montage est un
> objet physique unique : il ne peut pas être réparé de deux façons parce que
> deux add-ons l'ont déclaré différemment. Un second add-on qui déclare les
> mêmes montages les retrouve tels quels.

**Comportement en panne :**

| Mode | Ce qui se passe |
|---|---|
| **Repli local** *(défaut)* | L'add-on continue d'écrire en local, puis tout est rapatrié au retour du NAS. |
| **Arrêt seul** | L'add-on est arrêté dès la panne. Aucun fichier n'est déplacé. |

**Au rapatriement**, quand un fichier existe des deux côtés :

| Politique | Pour quoi |
|---|---|
| **Le plus récent gagne** *(défaut)* | Un autre appareil a pu écrire sur le partage pendant la panne. |
| **Le local écrase toujours** | L'add-on est le seul écrivain — le cas de Frigate. |
| **Ne jamais écraser le NAS** | Le partage fait autorité, le local n'est qu'un tampon. |

## La carte

Ajoutée automatiquement au sélecteur de cartes sous le nom **Add-on Mount
Guard**. En YAML :

```yaml
type: custom:mount-guard-card
entity: sensor.mount_guard_remediations
title: Montages surveillés
show_ok: true        # afficher les montages sains
show_history: false  # journal repliable sous chaque ligne
compact: false       # une ligne par montage, pour une tablette murale
mounts: []           # filtre ; vide = tous
```

Elle affiche, par montage : pastille d'état, add-ons concernés et leur état,
stepper des étapes avec l'étape active, barre de progression fichiers/octets,
fichier courant, temps écoulé, compte à rebours vers le prochain essai,
dernière erreur, et historique.

## Entités

Un appareil par **add-on** et un par **stockage réseau** :

| Entité | |
|---|---|
| `binary_sensor` par montage | `device_class: problem`, attributs = la remédiation complète |
| `sensor` État | `ok` / `local` / `repairing` / `stopped` |
| `sensor` Fichiers en attente | ce qui reste à rapatrier |
| `sensor` Dernier incident | horodatage |
| `button` Réparer | actif seulement quand il y a quelque chose à réparer |

Plus **`sensor.mount_guard_remediations`** : état = nombre de remédiations en
cours, attribut `remediations` = la liste complète. C'est ce que lit la carte.

## Services

| Service | |
|---|---|
| `addon_mount_guard.repair` | Lance la réparation sans attendre le délai de réessai. Cible un montage, un add-on (tous ses montages), ou rien (tout). |
| `addon_mount_guard.cancel` | Abandonne la remédiation en cours. Prend effet **entre deux étapes**, jamais au milieu d'une copie. |
| `addon_mount_guard.set_mode` | Change le comportement d'un montage en cas de panne. |

## Événements

`addon_mount_guard_event` est émis à **chaque changement d'état** d'un montage :

```yaml
automation:
  - triggers:
      - trigger: event
        event_type: addon_mount_guard_event
        event_data:
          to: degraded
    actions:
      - action: notify.mobile_app
        data:
          message: "Le montage {{ trigger.event.data.mount }} est tombé."
```

L'intégration **ne notifie pas elle-même** (hors notification persistante
optionnelle) : elle n'a pas à savoir si vous voulez une notification mobile,
une lampe rouge ou rien du tout.

## Limites

- **Home Assistant OS ou Supervised uniquement.** Sans Superviseur, il n'y a ni
  stockage réseau à surveiller ni add-on à arrêter. Le manifeste déclare
  `hassio` en dépendance : sur une installation Container ou Core, l'intégration
  ne se met simplement pas en place.
- **L'API du Superviseur n'est pas publique.** Tout passe par
  `homeassistant.components.hassio.get_supervisor_client`, exporté par le
  composant, mais rien ne garantit sa stabilité entre deux versions. Tous les
  appels sont regroupés dans `supervisor_api.py`, pour que la réparation se
  fasse à un seul endroit.
- **Un fichier écrit en local puis recouvert n'est pas récupérable.** Si le
  montage se rétablit **sans passer par la séquence** — typiquement un
  redémarrage de Home Assistant pendant que le NAS est revenu — les fichiers
  locaux passent sous le bind mount et deviennent invisibles depuis le conteneur.
  Démonter demanderait un accès à l'hôte que l'intégration n'a pas. Le cas est
  détecté et signalé dans le journal du montage, faute de mieux.
- **`/backup` n'est pas pris en charge** : il n'a pas de `<nom>` dans son chemin,
  donc la mise de côté écrirait `/backup_local` à la racine du conteneur, et
  aucun add-on n'y écrit en continu.
- **Aucun accès direct à l'hôte.** Tout passe par le Superviseur et par
  `/media` et `/share` tels que le conteneur core les voit.

## Version minimale de Home Assistant

**2026.1** — c'est une politique de support, plus qu'une dérivation des API
employées : seule la série 2026 est prise en charge.

## Développement

Voir [CLAUDE.md](CLAUDE.md) : invariants, pièges, et les commandes qui
reproduisent la CI.

## Licence

MIT — voir [LICENSE](LICENSE).
