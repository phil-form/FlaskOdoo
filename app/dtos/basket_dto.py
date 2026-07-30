from app.dtos.abstract_dto import AbstractDTO
from app.dtos.item_dto import ItemDTO
from app.dtos.user_dto import UserDTO
from app.models.basket import Basket


class BasketDTO(AbstractDTO):
    """Un panier: son propriétaire + ses lignes, déjà "aplaties" en ItemDTO."""

    def __init__(self):
        self.basket_id = None
        self.closed = None
        self.user = None         # UserDTO
        self.items = []          # liste d'ItemDTO

    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    def is_empty(self) -> bool:
        return len(self.items) == 0

    @staticmethod
    def build_from_entity(basket: Basket) -> "BasketDTO":
        basket_dto = BasketDTO()

        basket_dto.basket_id = basket.basket_id
        basket_dto.closed = basket.closed
        # Un panier peut exister sans user (cas limite), on protège l'accès.
        basket_dto.user = UserDTO.build_from_entity(basket.user) if basket.user else None
        # basket.items = des BasketItem: ItemDTO sait les lire (voir item_dto).
        basket_dto.items = [ItemDTO.build_from_entity(basket_item)
                            for basket_item in basket.items]

        return basket_dto

    def get_json_parsable(self):
        data = dict(self.__dict__)
        data['items'] = [item.get_json_parsable() for item in self.items]
        data['user'] = self.user.get_json_parsable() if self.user else None

        return data
