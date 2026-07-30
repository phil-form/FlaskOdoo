"""Controller de la page d'accueil.

Rôle d'un controller en MVC:
1. recevoir la requête HTTP,
2. valider les entrées (via un formulaire),
3. appeler un service,
4. choisir la réponse (un template à rendre ou une redirection).

À cette étape il n'y a pas encore de couche service: le controller interroge
donc la base lui-même. C'est provisoire — et c'est justement ce que l'étape
suivante corrige.
"""
from flask import render_template

from app import app
from app.models.item import Item


# app.get('/') est un raccourci pour app.route('/', methods=['GET'])
@app.get('/')
def index():
    # Le nom de la fonction devient le nom du "endpoint": c'est lui qu'on
    # utilise dans les templates avec url_for('index'). On ne code jamais une
    # URL en dur: si la route change, url_for suit.
    items = Item.query.filter_by(active=True).limit(3).all()

    return render_template('home/home.html', items=items)
