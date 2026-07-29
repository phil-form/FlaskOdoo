from pathlib import Path

# Les seeders du projet: les données de démonstration.
#
# Auto-découverte, comme pour les modèles, les controllers et les services:
# `from app.seed import *` (dans app/__init__.py) importe tous les modules du
# dossier. Et comme chaque `class XxxSeed(Seedable)` s'enregistre au moment où
# Python lit sa déclaration (voir Seedable.__init_subclass__), l'import suffit.
#
# Donc pour ajouter un jeu de données: créer un fichier ici, hériter de Seedable,
# implémenter seed(). Aucune liste à mettre à jour, aucun import à ajouter.

# Avec pathlib
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]
