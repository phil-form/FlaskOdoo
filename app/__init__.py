import random

from flask import Flask, render_template
from flask_debugtoolbar import DebugToolbarExtension
from dotenv import load_dotenv

app = Flask("app")
app.debug = True

app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = "TestAsdf1234="
toolbar = DebugToolbarExtension(app)

from app.controllers import *
