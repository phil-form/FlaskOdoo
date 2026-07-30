from pathlib import Path

# Package des services: toute la logique métier et les accès à la base.
# Voir app/services/base_service.py.
#
# Auto-découverte, comme pour les modèles et les controllers: `from app.services
# import *` (dans app/__init__.py) importe tous les modules du dossier.
#
# C'est indispensable depuis que le catalogue de l'injecteur est constitué par le
# décorateur @injectable: une classe ne s'enregistre qu'au moment où Python lit
# sa déclaration, donc à l'import de son module. Un service qu'aucun controller
# n'importe (AuthServiceImpl, par exemple) resterait invisible.

# Avec pathlib
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]
