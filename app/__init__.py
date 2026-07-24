import os
from pathlib import Path

from flask import Flask, render_template
from flask_debugtoolbar import DebugToolbarExtension
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, migrate
from sqlalchemy.cyextension.processors import to_str

from app.framework.seedable import Seedable

# Load les variables de .env
load_dotenv()

# Load les varibles de .env.local
env_path = Path().cwd() / '.env.local'
if os.path.exists(env_path):
    load_dotenv(env_path)
app = Flask("app")
app.debug = True

# Debug TOOLBAR
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = "TestAsdf1234="
toolbar = DebugToolbarExtension(app)

# SqlAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app.controllers import *
from app.models import *

@app.get('/seed')
def seed():
    import app.seed as seed

    for s in seed.__all__:
        c = s()
        if isinstance(c, Seedable):
            c.seed()


    return render_template('home/home.html',
                           ma_variable="Seeded",
                           items=[])
