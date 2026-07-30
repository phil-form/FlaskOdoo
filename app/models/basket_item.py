from app import db
from app.models.base_entity import BaseEntity


class BasketItem(BaseEntity, db.Model):
    """Ligne de panier: un article + une quantité, dans un panier donné.

    Encore une table d'association qui porte une donnée (la quantité), donc une
    entité à part entière. Clé primaire composée (item_id, basket_id): un
    article n'apparaît qu'une fois par panier, on incrémente sa quantité.
    """

    __tablename__ = "basket_items"

    item_id = db.Column(db.ForeignKey('items.item_id'), primary_key=True)
    basket_id = db.Column(db.ForeignKey('baskets.basket_id'), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    item = db.relationship('Item', back_populates='basket_items')
    basket = db.relationship('Basket', back_populates='items')

    def __repr__(self):
        return f"<BasketItem basket={self.basket_id} item={self.item_id} x{self.quantity}>"
