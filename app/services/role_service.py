from app.dtos.role_dto import RoleDTO
from app.framework.decorators.injectable import injectable
from app.models.role import Role
from app.services.base_service import BaseService


@injectable
class RoleService(BaseService):
    """Les rôles sont créés par les seeds et jamais modifiés par l'application.

    Le service n'expose donc que de la lecture. Les méthodes d'écriture du
    contrat BaseService restent volontairement non implémentées: on doit les
    déclarer (sinon la classe reste abstraite et Python refuse de l'instancier)
    mais elles lèvent une erreur explicite si quelqu'un les appelle un jour.
    """

    def find_all(self) -> list[RoleDTO]:
        return [RoleDTO.build_from_entity(role) for role in Role.query.all()]

    def find_all_entities(self) -> list[Role]:
        """Version entités, pour les usages internes (choices d'un formulaire,
        attribution d'un rôle à un user...)."""
        return Role.query.order_by(Role.role_id).all()

    def find_one(self, entity_id: int) -> RoleDTO | None:
        role = self.find_one_entity(entity_id)

        return RoleDTO.build_from_entity(role) if role else None

    def find_one_entity(self, entity_id: int) -> Role | None:
        # .first() rend None si rien ne correspond, .one() lèverait une
        # exception: on préfère un None qu'on peut tester.
        return Role.query.filter_by(role_id=entity_id).first()

    def find_one_by(self, **kwargs) -> Role | None:
        return Role.query.filter_by(**kwargs).first()

    def insert(self, data):
        raise NotImplementedError("Les rôles sont gérés par les seeds/migrations")

    def update(self, entity_id: int, data):
        raise NotImplementedError("Les rôles sont gérés par les seeds/migrations")

    def delete(self, entity_id: int):
        raise NotImplementedError("Les rôles sont gérés par les seeds/migrations")
