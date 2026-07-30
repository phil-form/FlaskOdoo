from flask_wtf import FlaskForm
from wtforms import IntegerField
from wtforms.validators import DataRequired, NumberRange


class BasketAddItemForm(FlaskForm):
    """Ajout / mise à jour d'une ligne de panier.

    item_id vient d'un <input hidden>: on ne fait donc AUCUNE confiance à sa
    valeur. Le service vérifiera que l'article existe vraiment, et le panier
    utilisé est toujours celui de l'utilisateur connecté (jamais un basket_id
    posté par le client).
    """

    item_id = IntegerField('item_id', validators=[DataRequired()])
    quantity = IntegerField('Quantité',
                            validators=[DataRequired(), NumberRange(min=1)])
