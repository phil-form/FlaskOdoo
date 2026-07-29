import os
import glob
from pathlib import Path

# Auto-découverte des controllers.
#
# Une route n'existe pour Flask que si le module qui contient son @app.route a
# été importé. Comme pour les modèles, on liste donc les modules du dossier et
# `from app.controllers import *` (dans app/__init__.py) les importe tous.
# Ajouter un controller = créer un fichier ici, rien d'autre.

# Version "à l'ancienne", avec os + glob:
# print(os.path.dirname(__file__))
# print(os.path.dirname(__file__) + "/*.py")
# print(glob.glob(os.path.dirname(__file__) + "/*.py"))
# print([os.path.basename(f)[:-3] for f in glob.glob(os.path.dirname(__file__) + "/*.py")])
# __all__ = [os.path.basename(f)[:-3] for f in glob.glob(os.path.dirname(__file__) + "/*.py")]

# Avec pathlib
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]
