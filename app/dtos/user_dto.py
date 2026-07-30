from app.dtos.abstract_dto import AbstractDTO
from app.dtos.role_dto import RoleDTO


class UserDTO(AbstractDTO):
    """Un utilisateur tel que le voient les templates.

    Remarquez ce qui n'est PAS là: le mot de passe. Un DTO ne transporte que ce
    dont la vue a besoin.
    """

    def __init__(self):
        self.user_id = None
        self.username = None
        self.email = None
        self.description = None
        self.email_verified = None
        self.roles = []          # liste de RoleDTO

    def role_names(self) -> list[str]:
        return [role.role_name for role in self.roles]

    def is_admin(self) -> bool:
        return "ADMIN" in self.role_names()

    @staticmethod
    def build_from_entity(user) -> "UserDTO":
        user_dto = UserDTO()

        user_dto.user_id = user.user_id
        user_dto.username = user.username
        user_dto.email = user.email
        user_dto.description = user.description
        user_dto.email_verified = user.email_verified
        # user.roles = des UserRole (table d'association), on remonte donc
        # jusqu'au Role via user_role.role.
        user_dto.roles = [RoleDTO.build_from_entity(user_role.role)
                          for user_role in user.roles]

        return user_dto

    def get_json_parsable(self):
        # Attention: on construit un NOUVEAU dictionnaire au lieu de modifier
        # self.__dict__, sinon l'appel abîmerait le DTO (self.roles
        # deviendrait une liste de dict et role_names() planterait).
        data = dict(self.__dict__)
        data['roles'] = [role.get_json_parsable() for role in self.roles]

        return data
