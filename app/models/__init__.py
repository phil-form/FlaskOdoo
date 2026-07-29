import os
import glob
from pathlib import Path

# Auto-découverte des modules du package.
#
# `from app.models import *` doit importer TOUS les modèles, sinon SQLAlchemy
# n'a pas connaissance de leurs tables (pas de mapping -> migrations vides,
# relations introuvables). Plutôt que de maintenir une liste d'imports à la
# main, on construit __all__ à partir du contenu du dossier.
#
# __all__ = ce que `from ... import *` exporte. Pour un package, y mettre des
# noms de modules force leur import.
#
# f.name[:-3] enlève les 3 caractères de ".py" -> le nom du module.
# La liste contient aussi "__init__", et ce n'est pas un problème: pour importer
# un nom de __all__, Python vérifie d'abord s'il existe déjà comme attribut du
# module, et tout objet possède un __init__. Il n'y a donc pas de réimport du
# package.

# Avec pathlib
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]
