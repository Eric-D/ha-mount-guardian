#!/usr/bin/env python3
"""Écrit les dépendances runtime du manifeste dans un fichier pip.

Le manifeste est la seule source de vérité : recopier ses bornes à la main dans
requirements_test.txt les laisserait diverger silencieusement au premier bump,
et la CI validerait alors contre un plancher périmé.

La liste est vide aujourd'hui — l'intégration n'a aucune dépendance runtime. Ce
script reste néanmoins branché dans la CI : le jour où une dépendance apparaît,
elle est prise en compte sans toucher aux workflows, ce qui est précisément le
genre d'oubli qu'on ne voit qu'en production.

Usage : python scripts/manifest_requirements.py [fichier-de-sortie]
"""
from __future__ import annotations

import json
import pathlib
import sys

# Relatif au script et non au répertoire courant : l'appelant n'a pas à se
# trouver à la racine du dépôt.
MANIFEST = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components/addon_mount_guard/manifest.json"
)


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "manifest-requirements.txt")
    requirements = json.loads(MANIFEST.read_text(encoding="utf-8"))["requirements"]
    # Le saut de ligne final compte même sur une liste vide : pip refuse un
    # fichier absent, pas un fichier vide.
    out.write_text("".join(f"{line}\n" for line in requirements), encoding="utf-8")
    print(f"{out} :", ", ".join(requirements) or "(aucune dépendance runtime)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
