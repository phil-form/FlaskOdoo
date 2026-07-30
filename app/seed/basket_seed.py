from app import app, db
from app.framework.seed import Seedable
from app.models.basket import Basket
from app.models.item import Item
from app.models.user import User


class BasketSeed(Seedable):
    """Remplit le panier du compte `test` pour avoir une page non vide.

    order = 40: il faut les users (20) ET les items (30).

    Ce seeder illustre un point important: on ne recrée pas la logique du
    modèle. On appelle basket.add_item(...), exactement comme le fait
    BasketService. Si la règle change (gestion du stock, prix...), elle change
    à un seul endroit.
    """

    order = 40

    # (username, nom de l'article, quantité)
    LINES = [
        ("test", "Clavier mécanique", 1),
        ("test", "Souris ergonomique", 2),
    ]

    def seed(self):
        for username, item_name, quantity in self.LINES:
            user = User.query.filter_by(username=username).first()
            item = Item.query.filter_by(name=item_name).first()

            if user is None or item is None:
                app.logger.warning(
                    f"Seed basket: user={username} ou item={item_name} introuvable")
                continue

            basket = user.current_basket()

            if basket is None:
                basket = Basket()
                basket.user = user
                db.session.add(basket)

            # add_item met simplement la quantité à jour si la ligne existe:
            # relancer /seed ne double donc pas les quantités.
            basket_item, exist = basket.add_item(item, quantity)

            if not exist:
                app.logger.debug(f"Seed basket {username}: +{quantity} {item_name}")
                db.session.add(basket_item)

        db.session.commit()
