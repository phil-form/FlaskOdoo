"""Controller du catalogue: liste et détail.

Comme home_controller à cette étape, il requête la base directement. Notez à
quel point le controller grossit dès qu'il porte la logique d'accès aux
données — le découpage en couches de l'étape suivante existe pour ça.
"""
from flask import flash, redirect, render_template, url_for

from app import app
from app.models.item import Item


@app.get('/items')
def item_list():
    items = Item.query.filter_by(active=True).order_by(Item.item_id).all()

    return render_template('items/list.html', items=items)


@app.get('/items/<int:item_id>')
def item_details(item_id: int):
    # <int:item_id> dans la route -> paramètre item_id de la fonction, déjà
    # converti en int par Flask (une URL /items/abc renvoie un 404).
    item = Item.query.filter_by(item_id=item_id).first()

    if item is None:
        # abort(404) serait plus correct HTTP, mais en MVC on préfère souvent
        # un message + redirection, plus agréable pour l'utilisateur.
        flash("Article introuvable.", "warning")
        return redirect(url_for('item_list'))

    return render_template('items/details.html', item=item)
