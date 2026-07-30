"""Controller du panier.

Point commun à toutes ces routes: aucune ne reçoit de basket_id. Le panier est
déduit de l'utilisateur connecté (auth_service.get_current_user()). Si on
acceptait un basket_id posté par le navigateur, il suffirait de changer un
champ caché pour remplir le panier du voisin.
"""
from flask import flash, redirect, render_template, request, url_for

from app import app
from app.forms.basket.basket_add_item_form import BasketAddItemForm
from app.framework.decorators.auth_required import auth_required
from app.framework.decorators.inject import inject
from app.services.auth_service import AuthService
from app.services.basket_service import BasketService


@app.get('/basket')
@auth_required()
@inject
def basket_details(basket_service: BasketService, auth_service: AuthService):
    user = auth_service.get_current_user()

    return render_template('baskets/details.html',
                           basket=basket_service.find_current(user.user_id),
                           history=basket_service.find_history(user.user_id),
                           add_form=BasketAddItemForm())


@app.post('/basket/add')
@auth_required()
@inject
def basket_add_item(basket_service: BasketService, auth_service: AuthService):
    form = BasketAddItemForm()

    if form.validate_on_submit():
        basket = basket_service.add_item(auth_service.get_current_user().user_id, form)

        if basket is None:
            flash("Impossible d'ajouter cet article.", "danger")
        else:
            flash("Panier mis à jour.", "success")
    else:
        # form.errors est un dict {champ: [messages]}. Ici on n'a pas de page
        # à réafficher (le formulaire est intégré dans une autre page), donc on
        # résume les erreurs dans un flash.
        flash(f"Formulaire invalide: {form.errors}", "danger")

    # request.referrer = la page d'où venait le formulaire: on y retourne pour
    # que l'utilisateur reprenne sa navigation où il l'avait laissée.
    # Il peut être absent (client sans en-tête Referer), d'où le `or`.
    return redirect(request.referrer or url_for('item_list'))


@app.post('/basket/remove/<int:item_id>')
@auth_required()
@inject
def basket_remove_item(item_id: int, basket_service: BasketService,
                       auth_service: AuthService):
    basket_service.remove_item(auth_service.get_current_user().user_id, item_id)
    flash("Article retiré du panier.", "info")

    return redirect(url_for('basket_details'))


@app.post('/basket/checkout')
@auth_required()
@inject
def basket_checkout(basket_service: BasketService, auth_service: AuthService):
    user = auth_service.get_current_user()

    # Une conséquence CONCRÈTE de la vérification d'adresse: on ne valide pas
    # une commande vers une adresse dont personne n'a prouvé l'existence.
    # C'est le bon dosage: on laisse entrer un compte non confirmé (il peut
    # regarder le catalogue), mais on bloque l'action qui engage.
    if not user.email_verified:
        flash("Confirmez votre adresse email avant de valider une commande.",
              "warning")
        return redirect(url_for('basket_details'))

    basket = basket_service.checkout(user.user_id)

    if basket is None:
        flash("Votre panier est vide.", "warning")
    else:
        flash(f"Commande n°{basket.basket_id} validée, merci!", "success")

    return redirect(url_for('basket_details'))


@app.get('/baskets')
@auth_required(level="ADMIN")
@inject
def basket_list(basket_service: BasketService):
    """Vue d'administration: tous les paniers de tous les utilisateurs."""
    return render_template('baskets/list.html', baskets=basket_service.find_all())
