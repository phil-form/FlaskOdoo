from app import app, db
from app.dtos.basket_dto import BasketDTO
from app.forms.basket.basket_add_item_form import BasketAddItemForm
from app.framework.decorators.injectable import injectable
from app.mappers.basket_mapper import BasketMapper
from app.models.basket import Basket
from app.models.item import Item
from app.services.base_service import BaseService


@injectable
class BasketService(BaseService):
    """Gestion des paniers.

    Règle de sécurité appliquée partout ici: le panier sur lequel on travaille
    est TOUJOURS retrouvé à partir du user_id de la session, jamais à partir
    d'un basket_id envoyé par le navigateur. Sinon n'importe qui pourrait
    ajouter des articles dans le panier de quelqu'un d'autre en changeant un
    champ caché.
    """

    # --- lecture ------------------------------------------------------------

    def find_all(self) -> list[BasketDTO]:
        return [BasketMapper.entity_to_dto(basket)
                for basket in Basket.query.order_by(Basket.basket_id).all()]

    def find_one(self, entity_id: int) -> BasketDTO | None:
        basket = Basket.query.filter_by(basket_id=entity_id).first()

        return BasketMapper.entity_to_dto(basket) if basket else None

    def find_one_by(self, **kwargs) -> BasketDTO | None:
        basket = Basket.query.filter_by(**kwargs).first()

        return BasketMapper.entity_to_dto(basket) if basket else None

    def find_current(self, user_id: int) -> BasketDTO:
        """Le panier ouvert de l'utilisateur (créé à la volée s'il n'existe pas)."""
        return BasketMapper.entity_to_dto(self.current_basket_entity(user_id))

    def find_history(self, user_id: int) -> list[BasketDTO]:
        """Les paniers déjà validés, du plus récent au plus ancien."""
        baskets = (Basket.query
                   .filter_by(user_id=user_id, closed=True)
                   .order_by(Basket.basket_id.desc())
                   .all())

        return [BasketMapper.entity_to_dto(basket) for basket in baskets]

    def current_basket_entity(self, user_id: int) -> Basket:
        """Retourne (et crée si besoin) le panier ouvert de l'utilisateur.

        Un user est censé toujours avoir un panier ouvert (créé à
        l'inscription), mais on ne s'appuie pas sur cette hypothèse: les
        comptes créés avant cette règle, ou juste après un checkout, doivent
        aussi fonctionner.
        """
        basket = Basket.query.filter_by(user_id=user_id, closed=False).first()

        if basket is None:
            basket = Basket()
            basket.user_id = user_id
            db.session.add(basket)
            db.session.commit()

        return basket

    # --- opérations métier --------------------------------------------------

    def add_item(self, user_id: int, form: BasketAddItemForm) -> BasketDTO | None:
        """Ajoute un article au panier, ou met à jour sa quantité."""
        item = Item.query.filter_by(item_id=form.item_id.data, active=True).first()

        if item is None:
            app.logger.warning(f"add_item: article {form.item_id.data} inconnu")
            return None

        quantity = form.quantity.data

        # Règle métier: on ne commande pas plus que le stock.
        if not item.in_stock(quantity):
            quantity = item.stock

        basket = self.current_basket_entity(user_id)
        # C'est le MODÈLE qui sait comment ajouter une ligne (voir Basket).
        basket_item, exist = basket.add_item(item, quantity)

        try:
            if not exist:
                db.session.add(basket_item)

            db.session.commit()
        except Exception as e:
            app.logger.error(f"add_item: {e}")
            db.session.rollback()
            return None

        return BasketMapper.entity_to_dto(basket)

    def remove_item(self, user_id: int, item_id: int) -> BasketDTO | None:
        basket = self.current_basket_entity(user_id)
        item = Item.query.filter_by(item_id=item_id).first()

        if item is None:
            return None

        try:
            basket.remove_item(item)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"remove_item: {e}")
            db.session.rollback()
            return None

        return BasketMapper.entity_to_dto(basket)

    def checkout(self, user_id: int) -> BasketDTO | None:
        """Valide le panier courant et en ouvre un nouveau.

        Deux écritures qui doivent réussir ensemble (fermer l'ancien, ouvrir le
        nouveau, décrémenter les stocks): un seul commit à la fin, donc une
        seule transaction. Si quelque chose échoue, le rollback annule tout.
        """
        basket = self.current_basket_entity(user_id)

        if not basket.items:
            return None

        try:
            for basket_item in basket.items:
                basket_item.item.stock = max(0, basket_item.item.stock - basket_item.quantity)

            basket.closed = True

            new_basket = Basket()
            new_basket.user_id = user_id
            db.session.add(new_basket)

            db.session.commit()
        except Exception as e:
            app.logger.error(f"checkout: {e}")
            db.session.rollback()
            return None

        return BasketMapper.entity_to_dto(basket)

    # --- contrat BaseService ------------------------------------------------

    def insert(self, data) -> BasketDTO:
        """Un panier n'est jamais créé depuis un formulaire: il naît avec le
        user, ou après un checkout."""
        raise NotImplementedError("Utilisez current_basket_entity(user_id)")

    def update(self, entity_id: int, data):
        raise NotImplementedError("Utilisez add_item / remove_item / checkout")

    def delete(self, entity_id: int) -> int | None:
        basket = Basket.query.filter_by(basket_id=entity_id).first()

        if basket is None:
            return None

        try:
            db.session.delete(basket)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"delete basket {entity_id}: {e}")
            db.session.rollback()
            return None

        return entity_id
