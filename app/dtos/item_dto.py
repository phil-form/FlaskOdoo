from app.dtos.abstract_dto import AbstractDTO
from app.models.basket_item import BasketItem
from app.models.item import Item


class ItemDTO(AbstractDTO):
    """Un article, vu du catalogue OU vu d'un panier.

    Le même DTO sait se construire depuis deux entités différentes:
    - Item        -> quantity = le stock disponible
    - BasketItem  -> quantity = la quantité commandée

    C'est pratique pour réutiliser le même tableau HTML dans les deux pages
    (voir templates/items/_item_table.html).
    """

    def __init__(self):
        self.item_id = None
        self.name = None
        self.description = None
        self.quantity = None
        self.stock = None

    @staticmethod
    def build_from_entity(entity) -> "ItemDTO":
        item_dto = ItemDTO()

        if isinstance(entity, Item):
            item_dto.item_id = entity.item_id
            item_dto.name = entity.name
            item_dto.description = entity.description
            item_dto.stock = entity.stock
            item_dto.quantity = entity.stock
        elif isinstance(entity, BasketItem):
            item_dto.item_id = entity.item.item_id
            item_dto.name = entity.item.name
            item_dto.description = entity.item.description
            item_dto.stock = entity.item.stock
            item_dto.quantity = entity.quantity

        return item_dto

    def get_json_parsable(self):
        return self.__dict__
