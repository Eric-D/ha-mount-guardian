"""Les deux tables qui relient add-ons et montages.

La surveillance et la réparation se font **par montage** ; seuls l'arrêt et le
redémarrage se font par add-on. Il faut donc lire la relation dans les deux
sens, et c'est la seule raison d'être de ce module :

- `mount -> [slugs]` : **qui arrêter** quand un montage tombe ;
- `slug -> [mounts]` : **a-t-on le droit de relancer** cet add-on.

La seconde est celle qu'on oublie. Sans elle, la réparation de `nas_media`
relancerait Frigate alors que `nas_config`, son autre montage, attend d'être
réparé à son tour — il faudrait le rearrêter dans la minute, et entre les deux
il écrirait en local exactement ce qu'on venait de rapatrier.

Module pur : aucun import de Home Assistant, aucune E/S. Il doit le rester.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .const import DEFAULT_OVERWRITE, USAGE_ROOTS

_LOGGER = logging.getLogger(__name__)


def mount_path(name: str, usage: str) -> str:
    """Chemin du montage **tel que le conteneur core le voit**.

    Dérivé, jamais stocké ni lu du Supervisor. Stocké, il deviendrait faux le
    jour où l'utilisateur changerait l'usage d'un montage sans repasser par le
    flux ; lu du Supervisor, il décrirait ce que voit l'hôte, alors que ce qui
    compte est le point où Home Assistant écrit — et c'est justement là que le
    bind mount peut manquer pendant que le Supervisor annonce le montage actif.
    """
    return f"{USAGE_ROOTS[usage]}/{name}"


@dataclass(frozen=True, slots=True)
class MountConfig:
    """Un montage surveillé et les add-ons qui en dépendent.

    `mode` et `host` sont des propriétés du **montage**, pas de la paire
    add-on↔montage : un montage est un objet physique unique, il ne peut pas
    être réparé de deux façons parce que deux add-ons l'ont déclaré
    différemment. Ils vivent donc dans les options de l'entrée, et la
    sous-entrée d'un add-on ne fait que nommer les montages qu'il utilise. Le
    conflit n'est pas arbitré, il est rendu impossible.
    """

    mount: str
    path: str
    host: str
    mode: str
    usage: str
    #: Triés alphabétiquement, et c'est structurel : c'est dans cet ordre que
    #: `repair.py` prend ses verrous par add-on. Un ordre variable entre deux
    #: remédiations partageant partiellement leurs add-ons produirait un
    #: interblocage, qui ne se verrait qu'en production et seulement parfois.
    slugs: tuple[str, ...]
    #: Politique de rapatriement, elle aussi propriété du montage : c'est le
    #: contenu du partage qui décide qui fait autorité, pas l'add-on qui le
    #: lit. Défaut en dernier, donc déclaré en dernier — les champs sans défaut
    #: doivent précéder.
    overwrite: str = DEFAULT_OVERWRITE


@dataclass(frozen=True, slots=True)
class MountTable:
    """Les deux sens de la relation, construits ensemble.

    Ensemble et non à la demande : dérivés l'un de l'autre au moment de s'en
    servir, ils pourraient décrire deux configurations différentes si une
    sous-entrée changeait entre les deux lectures.
    """

    mounts: Mapping[str, MountConfig]
    by_addon: Mapping[str, tuple[str, ...]]

    def slugs_for(self, mount: str) -> tuple[str, ...]:
        config = self.mounts.get(mount)
        return config.slugs if config else ()

    def mounts_for(self, slug: str) -> tuple[str, ...]:
        return self.by_addon.get(slug, ())

    def other_mounts_of(self, slug: str, mount: str) -> tuple[str, ...]:
        """Les autres montages de cet add-on. La question posée avant chaque
        relance, et la raison d'être de `by_addon`."""
        return tuple(name for name in self.mounts_for(slug) if name != mount)


def build_mount_table(
    mount_options: Mapping[str, Mapping[str, Any]],
    subentries: Iterable[Mapping[str, Any]],
) -> MountTable:
    """Construit les deux tables à partir de la configuration.

    `mount_options` : les options de l'entrée, `{<nom>: {host, mode, usage}}`.
    `subentries` : les sous-entrées, `{"slug": ..., "mounts": [<noms>]}`.

    Deux incohérences sont tolérées plutôt que levées, parce que toutes deux
    arrivent normalement pendant l'édition de la configuration et qu'une
    exception ici empêcherait l'entrée de se charger :

    - un add-on citant un montage absent des options (montage supprimé, ou
      sous-entrée ajoutée avant lui) : la référence est ignorée ;
    - un montage qu'aucun add-on ne cite (dernière sous-entrée supprimée) : le
      montage est écarté de la surveillance.

    Le second mérite sa raison. On pourrait vouloir surveiller un montage sans
    add-on, et le recharger quand le NAS revient. **Non** : la séquence de
    réparation déplace des fichiers. Elle existe pour arbitrer entre un add-on
    qui écrit et un montage qui a disparu sous lui ; sans add-on, il n'y a
    personne dont on connaisse l'écriture, et déplacer le contenu de `/media/x`
    parce qu'un montage est tombé serait une initiative que rien n'a demandée.
    """
    by_addon: dict[str, tuple[str, ...]] = {}
    slugs_by_mount: dict[str, set[str]] = {}

    for subentry in subentries:
        slug = subentry.get("slug")
        if not slug:
            continue
        names: list[str] = []
        for name in subentry.get("mounts", ()):
            if name not in mount_options:
                _LOGGER.warning(
                    "Add-on %s : montage %s inconnu des options, référence ignorée", slug, name
                )
                continue
            if name in names:
                # Déclaré deux fois par le même add-on : sans déduplication il
                # serait arrêté deux fois, et le compte des add-ons affiché sur
                # la carte serait faux.
                continue
            names.append(name)
            slugs_by_mount.setdefault(name, set()).add(slug)
        if names:
            # Triés : c'est l'ordre dans lequel `repair.py` prend ses verrous.
            by_addon[slug] = tuple(sorted(names))

    mounts: dict[str, MountConfig] = {}
    for name, options in mount_options.items():
        slugs = slugs_by_mount.get(name)
        if not slugs:
            _LOGGER.debug("Montage %s cité par aucun add-on, hors surveillance", name)
            continue
        usage = options["usage"]
        mounts[name] = MountConfig(
            mount=name,
            path=mount_path(name, usage),
            host=options["host"],
            mode=options["mode"],
            usage=usage,
            slugs=tuple(sorted(slugs)),
            overwrite=options.get("overwrite", DEFAULT_OVERWRITE),
        )

    # Purge symétrique : un add-on dont tous les montages ont été écartés ne
    # doit pas rester dans `by_addon`, sinon `other_mounts_of` renverrait des
    # noms que `mounts` ne connaît pas et la garde de relance interrogerait un
    # état inexistant.
    by_addon = {
        slug: tuple(name for name in names if name in mounts)
        for slug, names in by_addon.items()
    }
    by_addon = {slug: names for slug, names in by_addon.items() if names}

    return MountTable(mounts=mounts, by_addon=by_addon)
