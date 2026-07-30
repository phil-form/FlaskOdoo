from app import db
from app.models.base_entity import BaseEntity
from app.models.basket_item import BasketItem
from app.models.item import Item


class Basket(BaseEntity, db.Model):
    """Le panier d'un utilisateur.

    Un user a plusieurs paniers: un seul ouvert (closed=False, celui en cours)
    et l'historique des paniers validés (closed=True). Valider un panier ne le
    supprime donc pas, on en ouvre simplement un nouveau.
    """

    __tablename__ = "baskets"

    basket_id = db.Column(db.Integer, primary_key=True)
    closed = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.ForeignKey('users.user_id'))

    user = db.relationship("User", back_populates="baskets")
    items = db.relationship("BasketItem", back_populates='basket',
                            cascade='all, delete-orphan')

    # --- logique métier -----------------------------------------------------

    def add_item(self, item: Item, quantity: int):
        """Ajoute un article, ou met à jour sa quantité s'il est déjà là.

        Retourne (ligne_de_panier, existait_déjà) pour que le service sache
        s'il doit faire un db.session.add().
        """
        basket_item = self.find_item(item)
        exist = True

        if basket_item is None:
            exist = False
            basket_item = BasketItem()
            basket_item.item = item
            basket_item.basket = self
            self.items.append(basket_item)

        basket_item.quantity = quantity

        return basket_item, exist

    def remove_item(self, item: Item):
        """Retire complètement un article du panier."""
        basket_item = self.find_item(item)

        if basket_item is not None:
            # Grâce à delete-orphan, retirer la ligne de la collection suffit:
            # SQLAlchemy fera le DELETE au commit.
            self.items.remove(basket_item)

    def find_item(self, item: Item) -> BasketItem | None:
        for basket_item in self.items:
            if item.item_id == basket_item.item_id:
                return basket_item

        return None

    def total_quantity(self) -> int:
        return sum(basket_item.quantity for basket_item in self.items)

    def __repr__(self):
        return f"<Basket {self.basket_id} closed={self.closed}>"
