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
from app.services.item_service import ItemService


@app.get('/')
def index():
    # Le service est construit à la main: c'est le controller qui décide de
    # l'implémentation, et il faudra éditer toutes les vues pour en changer.
    # L'étape « injection de dépendances » supprime cette ligne.
    item_service = ItemService()

    return render_template('home/home.html',
                           items=item_service.find_all()[:3])
