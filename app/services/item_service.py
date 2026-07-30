from app import app, db
from app.dtos.item_dto import ItemDTO
from app.forms.item.item_form import ItemForm
from app.framework.decorators.injectable import injectable
from app.mappers.item_mapper import ItemMapper
from app.models.item import Item
from app.services.base_service import BaseService


# @injectable nu = enregistré sous son propre nom, en SINGLETON: le service est
# sans état, une seule instance suffit pour toute l'application.
@injectable
class ItemService(BaseService):
    """CRUD du catalogue. C'est le service le plus simple: prenez-le comme
    modèle quand vous ajoutez une nouvelle entité."""

    def find_all(self) -> list[ItemDTO]:
        return [ItemMapper.entity_to_dto(item)
                for item in Item.query.filter_by(active=True).order_by(Item.item_id).all()]

    def find_one(self, entity_id: int) -> ItemDTO | None:
        item = self.find_one_entity(entity_id)

        return ItemMapper.entity_to_dto(item) if item else None

    def find_one_entity(self, entity_id: int) -> Item | None:
        return Item.query.filter_by(item_id=entity_id).first()

    def find_one_by(self, **kwargs) -> ItemDTO | None:
        item = Item.query.filter_by(**kwargs).first()

        return ItemMapper.entity_to_dto(item) if item else None

    def insert(self, form: ItemForm) -> ItemDTO | None:
        item = Item()
        ItemMapper.form_to_entity(form, item)

        try:
            # add() ne fait rien en base: il attache l'objet à la session.
            # C'est commit() qui déclenche l'INSERT (et remplit item.item_id).
            db.session.add(item)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"insert item: {e}")
            # Sans rollback, la session reste "cassée" et toutes les requêtes
            # suivantes de la même requête HTTP échouent aussi.
            db.session.rollback()
            return None

        return ItemMapper.entity_to_dto(item)

    def update(self, entity_id: int, form: ItemForm) -> ItemDTO | None:
        item = self.find_one_entity(entity_id)

        if item is None:
            return None

        # Pas de add() ici: l'entité vient d'une requête, elle est déjà suivie
        # par la session. Modifier ses attributs suffit, commit() génère
        # l'UPDATE (c'est le "dirty tracking" de l'ORM).
        ItemMapper.form_to_entity(form, item)

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"update item {entity_id}: {e}")
            db.session.rollback()
            return None

        return ItemMapper.entity_to_dto(item)

    def delete(self, entity_id: int) -> int | None:
        item = self.find_one_entity(entity_id)

        if item is None:
            return None

        try:
            # Suppression réelle: la cascade sur Item.basket_items retire
            # l'article des paniers où il se trouvait.
            db.session.delete(item)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"delete item {entity_id}: {e}")
            db.session.rollback()
            return None

        return entity_id
