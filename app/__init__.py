from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from dotenv import load_dotenv

app = Flask("app")
app.debug = True

app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = "TestAsdf1234="
toolbar = DebugToolbarExtension(app)

@app.get('/')
def test():
    return """
    <h1>Hello</h1>
    <p>Mon super texte !!!</p>
    """

@app.get('/autre')
def test2():
    return """
    <h1>Mon autre page</h1>
    """