from app import db
from app.models.base_entity import BaseEntity
from app.models.role import Role
from app.models.user_role import UserRole


class User(BaseEntity, db.Model):
    """Un utilisateur du site.

    Le mot de passe n'est JAMAIS stocké en clair: la colonne contient un hash
    argon2 (voir UserService.insert). On ne peut pas "décoder" un hash, on peut
    seulement revérifier un mot de passe candidat.
    """

    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    # 255 caractères: un hash argon2 fait ~100 caractères, on prévoit large.
    password = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=False, default="",
                            server_default="")
    # Adresse confirmée par un lien reçu par mail (voir
    # EmailVerificationService). server_default=false: les comptes existants au
    # moment de la migration doivent recevoir une valeur.
    email_verified = db.Column(db.Boolean, nullable=False, default=False,
                               server_default=db.false())

    # cascade='all, delete-orphan': supprimer un user supprime ses lignes
    # d'association (sinon la base refuserait, à cause des clés étrangères).
    roles = db.relationship('UserRole', back_populates='user',
                            cascade='all, delete-orphan')
    baskets = db.relationship('Basket', back_populates='user',
                              cascade='all, delete-orphan')

    # --- logique métier -----------------------------------------------------
    # Un modèle n'est pas qu'un sac de colonnes: les règles qui ne concernent
    # que l'entité elle-même vivent ici, pas dans le service ni le controller.

    def add_role(self, role: Role):
        """Ajoute un rôle (sans doublon)."""
        if role.role_name in self.role_names():
            return

        user_role = UserRole()
        user_role.role = role
        user_role.user = self
        self.roles.append(user_role)

    def remove_role(self, role: Role):
        """Retire un rôle s'il est présent."""
        for user_role in self.roles:
            if user_role.role.role_name == role.role_name:
                self.roles.remove(user_role)
                break

    def role_names(self) -> list[str]:
        return [user_role.role.role_name for user_role in self.roles]

    def is_admin(self) -> bool:
        return "ADMIN" in self.role_names()

    def current_basket(self):
        """Le panier en cours (non validé), ou None."""
        for basket in self.baskets:
            if not basket.closed:
                return basket

        return None

    def __repr__(self):
        return f"<User {self.username}>"
