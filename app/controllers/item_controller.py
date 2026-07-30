"""Controller du catalogue: c'est le CRUD de référence du projet.

Les cinq routes typiques d'une ressource en MVC:

    GET  /items              liste
    GET  /items/<id>         détail
    GET  /items/add          formulaire de création       (+ POST pour créer)
    GET  /items/<id>/edit    formulaire de modification   (+ POST pour modifier)
    POST /items/<id>/delete  suppression

En API REST on utiliserait les verbes PUT et DELETE, mais un formulaire HTML ne
sait envoyer que GET et POST: en MVC on reste donc sur POST pour toute action
qui modifie quelque chose.
"""
from flask import flash, redirect, render_template, url_for

from app import app
from app.forms.basket.basket_add_item_form import BasketAddItemForm
from app.forms.item.item_form import ItemForm
from app.framework.decorators.auth_required import auth_required
from app.framework.decorators.inject import inject
from app.services.item_service import ItemService


@app.get('/items')
@inject
def item_list(item_service: ItemService):
    # add_form: le petit formulaire "ajouter au panier" affiché sur chaque
    # ligne. On l'instancie ici uniquement pour son jeton CSRF, que le template
    # rend avec form.csrf_token.
    return render_template('items/list.html',
                           items=item_service.find_all(),
                           add_form=BasketAddItemForm())


@app.get('/items/<int:item_id>')
@inject
def item_details(item_id: int, item_service: ItemService):
    item = item_service.find_one(item_id)

    if item is None:
        flash("Article introuvable.", "warning")
        return redirect(url_for('item_list'))

    return render_template('items/details.html',
                           item=item,
                           add_form=BasketAddItemForm())


@app.route('/items/add', methods=['GET', 'POST'])
@auth_required(level="ADMIN")
@inject
def item_add(item_service: ItemService):
    form = ItemForm()

    if form.validate_on_submit():
        item = item_service.insert(form)

        if item is None:
            flash("Impossible de créer l'article (nom déjà pris?).", "danger")
        else:
            flash(f"Article « {item.name} » créé.", "success")
            return redirect(url_for('item_list'))

    # Le même template sert à créer et à modifier: seule l'action du <form>
    # change, et elle est calculée dans le template à partir de `item`.
    return render_template('items/add_or_update.html', form=form, item=None)


@app.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@auth_required(level="ADMIN")
@inject
def item_update(item_id: int, item_service: ItemService):
    item = item_service.find_one(item_id)

    if item is None:
        flash("Article introuvable.", "warning")
        return redirect(url_for('item_list'))

    # obj=item: WTForms recopie item.name, item.description, item.stock dans
    # les champs du même nom -> formulaire pré-rempli sans effort.
    # En POST, les données envoyées ont la priorité sur obj.
    form = ItemForm(obj=item)

    if form.validate_on_submit():
        updated = item_service.update(item_id, form)

        if updated is None:
            flash("Modification impossible (nom déjà pris?).", "danger")
        else:
            flash("Article mis à jour.", "success")
            return redirect(url_for('item_details', item_id=item_id))

    return render_template('items/add_or_update.html', form=form, item=item)


@app.post('/items/<int:item_id>/delete')
@auth_required(level="ADMIN")
@inject
def item_delete(item_id: int, item_service: ItemService):
    if item_service.delete(item_id) is None:
        flash("Suppression impossible.", "danger")
    else:
        flash("Article supprimé.", "success")

    return redirect(url_for('item_list'))
