from app.dtos.basket_dto import BasketDTO
from app.mappers.abstract_mapper import AbstractMapper
from app.models.basket import Basket


class BasketMapper(AbstractMapper):
    @staticmethod
    def entity_to_dto(entity: Basket) -> BasketDTO:
        return BasketDTO.build_from_entity(entity)

    @staticmethod
    def form_to_entity(form, basket: Basket) -> Basket:
        """Rien à recopier ici.

        Un panier n'a aucun champ éditable directement par l'utilisateur: on
        n'agit dessus qu'à travers des opérations métier (add_item,
        remove_item, checkout). Le mapper existe quand même pour respecter le
        contrat AbstractMapper — et pour montrer que toutes les entités n'ont
        pas besoin d'un formulaire.
        """
        return basket
