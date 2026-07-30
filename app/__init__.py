"""Point d'entrée de l'application: création de l'objet Flask et câblage.

Ce fichier est exécuté une seule fois, au premier `import app`. Son ordre est
important, il se lit de haut en bas:

1. charger la configuration (.env)
2. créer `app` (l'objet Flask) et `db` (SQLAlchemy)
3. importer les modèles et les controllers
4. importer les seeds (qui ajoutent la route /seed en debug)

Pourquoi les imports des étapes 3 et 4 sont-ils EN BAS du fichier et pas en haut
comme le veut PEP8? Parce que app/controllers/xxx.py fait `from app import app`:
le module app doit donc déjà exister et contenir `app` au moment de cet import.
C'est l'import circulaire classique d'une application Flask construite autour
d'un objet `app` global. Python l'accepte parce qu'à ce stade `app` est déjà
défini dans le module en cours de chargement.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# Load les variables de .env
load_dotenv()

# Load les varibles de .env.local (git-ignoré: c'est là que vont les secrets et
# les réglages propres à votre machine, il écrase donc .env)
env_path = Path().cwd() / '.env.local'
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

app = Flask("app")
# DEBUG=... dans le .env. Attention au piège: une variable d'environnement est
# TOUJOURS une chaîne, et bool("False") vaut True. D'où la comparaison explicite.
app.debug = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")

# La clé qui signe les cookies de session.
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "TestAsdf1234=")

# Protection CSRF globale.
# FlaskForm valide déjà son jeton, mais CSRFProtect étend le contrôle à TOUTES
# les requêtes POST/PUT/DELETE, y compris celles qui n'ont pas de formulaire
# WTForms (nos boutons "supprimer", par exemple). Sans lui, ces routes seraient
# déclenchables depuis n'importe quel site tiers.
# Effet de bord pratique: la fonction csrf_token() devient disponible dans les
# templates.
csrf = CSRFProtect(app)

# Debug TOOLBAR
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
toolbar = DebugToolbarExtension(app)

# SqlAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
# TRACK_MODIFICATIONS: système d'événements coûteux dont on ne se sert pas.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- 3) modèles et controllers ---------------------------------------------
# Ces deux imports en étoile chargent TOUS les fichiers des deux dossiers
# (voir le __all__ construit dynamiquement dans leurs __init__.py).
# Les modèles doivent être importés pour que SQLAlchemy connaisse les tables,
# les controllers pour que leurs @app.route s'enregistrent.
from app.models import *
from app.controllers import *

# --- 4) seeds ---------------------------------------------------------------
# Même mécanisme: l'import en étoile charge tous les fichiers de app/seed/, et
# chaque `class XxxSeed(Seedable)` s'enregistre à sa déclaration. Seed(app) n'a
# donc plus qu'à ajouter la route /seed — et uniquement si app.debug est vrai.
from app.seed import *
from app.framework.seed import Seed

seed = Seed(app)
