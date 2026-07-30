"""Controller de la page d'accueil.

Rôle d'un controller en MVC:
1. recevoir la requête HTTP,
2. valider les entrées (via un formulaire),
3. appeler un service,
4. choisir la réponse (un template à rendre ou une redirection).

Ce qu'un controller ne fait JAMAIS: une requête SQL, un calcul métier, ou du
formatage compliqué. Le premier va dans le service, le deuxième dans le modèle,
le troisième dans le template.
"""
from flask import render_template

from app import app
from app.framework.decorators.inject import inject
from app.services.item_service import ItemService


# app.get('/') est un raccourci pour app.route('/', methods=['GET'])
@app.get('/')
@inject
def index(item_service: ItemService):
    # Le nom de la fonction devient le nom du "endpoint": c'est lui qu'on
    # utilise dans les templates avec url_for('index'). On ne code jamais une
    # URL en dur: si la route change, url_for suit.
    return render_template('home/home.html',
                           items=item_service.find_all()[:3])
