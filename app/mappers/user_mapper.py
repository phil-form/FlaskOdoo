from app.dtos.user_dto import UserDTO
from app.forms.user.user_login_form import UserLoginForm
from app.forms.user.user_register_form import UserRegisterForm
from app.forms.user.user_update_form import UserUpdateForm
from app.mappers.abstract_mapper import AbstractMapper
from app.models.user import User


class UserMapper(AbstractMapper):
    @staticmethod
    def entity_to_dto(entity: User) -> UserDTO:
        return UserDTO.build_from_entity(entity)

    @staticmethod
    def form_to_entity(form, user: User) -> User:
        """Reporte les champs du formulaire sur l'entité.

        Un seul mapper pour plusieurs formulaires: on regarde le type reçu.
        Chaque branche ne copie QUE les champs de ce formulaire — c'est ce qui
        garantit qu'un POST sur /profile/edit ne peut pas modifier le mot de
        passe ou le username, même si le navigateur les envoie.

        Le mot de passe est copié tel quel (en clair): c'est UserService qui le
        hashe juste après. Le mapper ne fait que traduire.
        """
        if isinstance(form, UserRegisterForm):
            user.username = form.username.data
            user.email = form.email.data
            user.password = form.password.data
            user.description = form.description.data or ""

        elif isinstance(form, UserUpdateForm):
            user.email = form.email.data
            user.description = form.description.data or ""
            # Les rôles ne sont PAS appliqués ici: c'est une opération
            # privilégiée, gérée par UserService.update après vérification des
            # droits de l'utilisateur connecté.

        elif isinstance(form, UserLoginForm):
            user.username = form.username.data
            user.password = form.password.data

        return user
