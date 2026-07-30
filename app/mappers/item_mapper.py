from app.dtos.item_dto import ItemDTO
from app.forms.item.item_form import ItemForm
from app.mappers.abstract_mapper import AbstractMapper
from app.models.item import Item


class ItemMapper(AbstractMapper):
    @staticmethod
    def entity_to_dto(item: Item) -> ItemDTO:
        return ItemDTO.build_from_entity(item)

    @staticmethod
    def form_to_entity(form, item: Item) -> Item:
        if isinstance(form, ItemForm):
            item.name = form.name.data
            item.description = form.description.data
            item.stock = form.stock.data

        return item
