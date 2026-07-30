from app import db
from app.models.base_entity import BaseEntity


class Item(BaseEntity, db.Model):
    """Un article du catalogue."""

    __tablename__ = "items"

    item_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True, unique=True)
    # Text = longueur illimitée (contrairement à String(255)).
    description = db.Column(db.Text, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=1)

    # Les lignes de panier qui pointent vers cet article. La cascade permet de
    # supprimer un article même s'il est dans des paniers: ses lignes de panier
    # partent avec lui.
    basket_items = db.relationship('BasketItem', back_populates='item',
                                   cascade='all, delete-orphan')

    def in_stock(self, quantity: int = 1) -> bool:
        return self.stock >= quantity

    def __repr__(self):
        return f"<Item {self.name}>"
