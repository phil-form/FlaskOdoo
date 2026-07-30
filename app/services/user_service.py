from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app import app, db
from app.dtos.user_dto import UserDTO
from app.forms.user.user_login_form import UserLoginForm
from app.forms.user.user_register_form import UserRegisterForm
from app.forms.user.user_update_form import UserUpdateForm
from app.framework.decorators.injectable import injectable
from app.mappers.user_mapper import UserMapper
from app.models.basket import Basket
from app.models.role import Role
from app.models.user import User
from app.services.base_service import BaseService


@injectable
class UserService(BaseService):
    """Tout ce qui concerne les utilisateurs: CRUD + inscription + connexion."""

    def __init__(self):
        # argon2 est le hachage de mots de passe recommandé aujourd'hui
        # (vainqueur de la Password Hashing Competition). Le PasswordHasher
        # gère lui-même le sel: il est inclus dans la chaîne produite par
        # hash(), on n'a donc pas de colonne "salt" à stocker.
        self.__hasher = PasswordHasher()

    # --- lecture ------------------------------------------------------------

    def find_all(self) -> list[UserDTO]:
        # active=True: on ne montre pas les comptes désactivés (soft delete).
        return [UserMapper.entity_to_dto(user)
                for user in User.query.filter_by(active=True).order_by(User.user_id).all()]

    def find_one(self, entity_id: int) -> UserDTO | None:
        user = self.find_one_entity(entity_id)

        return UserMapper.entity_to_dto(user) if user else None

    def find_one_entity(self, entity_id: int) -> User | None:
        return User.query.filter_by(user_id=entity_id).first()

    def find_one_by(self, **kwargs) -> User | None:
        """Retourne une ENTITÉ (utilisé par le login, qui a besoin du hash)."""
        return User.query.filter_by(**kwargs).first()

    # --- écriture -----------------------------------------------------------

    def insert(self, form: UserRegisterForm) -> UserDTO | None:
        """Inscription d'un nouvel utilisateur."""
        user = User()
        UserMapper.form_to_entity(form, user)

        # Le mapper a mis le mot de passe en clair, on le remplace par son hash
        # AVANT tout contact avec la base.
        user.password = self.__hasher.hash(user.password)

        # Tout nouveau compte est un simple USER...
        role_user = Role.query.filter_by(role_name="USER").first()
        if role_user is not None:
            user.add_role(role_user)

        # ... et démarre avec un panier vide ouvert.
        user.baskets.append(Basket())

        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            # Cas typique: username ou email déjà pris (contrainte unique).
            app.logger.error(f"insert user: {e}")
            db.session.rollback()
            return None

        return UserMapper.entity_to_dto(user)

    def update(self, entity_id: int, form: UserUpdateForm) -> UserDTO | None:
        """Met à jour les champs non sensibles (email, description)."""
        user = self.find_one_entity(entity_id)

        if user is None:
            return None

        UserMapper.form_to_entity(form, user)

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"update user {entity_id}: {e}")
            db.session.rollback()
            return None

        return UserMapper.entity_to_dto(user)

    def mark_email_verified(self, entity_id: int) -> UserDTO | None:
        """Confirme l'adresse email (appelé par EmailVerificationService)."""
        user = self.find_one_entity(entity_id)

        if user is None:
            return None

        user.email_verified = True

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"mark email verified {entity_id}: {e}")
            db.session.rollback()
            return None

        return UserMapper.entity_to_dto(user)

    def update_password(self, entity_id: int, plain_password: str) -> UserDTO | None:
        """Remplace le mot de passe (réinitialisation par mail).

        Séparée de update(): ce n'est pas un champ de formulaire de profil, et le
        hachage doit rester au même endroit que celui de l'inscription.

        Effet de bord voulu: changer le hash invalide les liens de
        réinitialisation en circulation (voir PasswordResetService, l'empreinte
        embarquée dans le token ne correspond plus).
        """
        user = self.find_one_entity(entity_id)

        if user is None:
            return None

        user.password = self.__hasher.hash(plain_password)

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"update password {entity_id}: {e}")
            db.session.rollback()
            return None

        return UserMapper.entity_to_dto(user)

    def update_roles(self, entity_id: int, roles: list[Role]) -> UserDTO | None:
        """Remplace la liste des rôles d'un utilisateur.

        Méthode séparée de update() parce que c'est une opération privilégiée:
        le controller ne l'appelle que si l'utilisateur connecté est ADMIN.
        Un champ "rôles" posté par un non-admin est donc simplement ignoré,
        même s'il passe la validation du formulaire.
        """
        user = self.find_one_entity(entity_id)

        if user is None:
            return None

        wanted = [role.role_name for role in roles]

        for role in roles:
            user.add_role(role)

        # Retirer ceux qui ne sont plus cochés. On itère sur une copie de la
        # liste (list(...)) car remove_role modifie user.roles pendant la
        # boucle.
        for user_role in list(user.roles):
            if user_role.role.role_name not in wanted:
                user.remove_role(user_role.role)

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"update roles {entity_id}: {e}")
            db.session.rollback()
            return None

        return UserMapper.entity_to_dto(user)

    def delete(self, entity_id: int) -> int | None:
        """Suppression logique (soft delete): le compte est désactivé.

        On ne fait pas de DELETE réel pour garder l'historique des paniers.
        Pour une vraie suppression: db.session.delete(user) — les cascades
        déclarées sur les relations emportent rôles et paniers.
        """
        user = self.find_one_entity(entity_id)

        if user is None:
            return None

        user.soft_delete()

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"delete user {entity_id}: {e}")
            db.session.rollback()
            return None

        return user.user_id

    # --- authentification ---------------------------------------------------

    def login(self, form: UserLoginForm) -> UserDTO | None:
        """Vérifie les identifiants. Retourne le DTO du user, ou None."""
        candidate = User()
        UserMapper.form_to_entity(form, candidate)

        user = self.find_one_by(username=candidate.username, active=True)

        if user is None:
            # Utilisateur inconnu. On pourrait s'arrêter là, mais répondre
            # instantanément alors qu'un mauvais mot de passe prend ~50ms
            # permet de deviner quels comptes existent (timing attack).
            # On hashe donc dans le vide pour égaliser les temps de réponse.
            self.__hasher.hash(candidate.password)
            return None

        try:
            # verify() lève une exception si ça ne correspond pas,
            # elle ne retourne pas False.
            self.__hasher.verify(user.password, candidate.password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None

        # argon2 évolue (paramètres de coût plus élevés avec le temps):
        # si le hash stocké est obsolète, on le remplace maintenant qu'on a le
        # mot de passe en clair sous la main.
        if self.__hasher.check_needs_rehash(user.password):
            user.password = self.__hasher.hash(candidate.password)
            db.session.commit()

        return UserMapper.entity_to_dto(user)
