from app import db
from app.models.base_entity import BaseEntity


class UserRole(BaseEntity, db.Model):
    """Table d'association User <-> Role (many-to-many).

    Pourquoi une classe et pas un simple db.Table? Parce qu'on veut pouvoir y
    ajouter des colonnes (ici celles de BaseEntity: qui/quand a reçu le rôle).
    Dès qu'une table de liaison porte des données, on en fait une entité.

    La clé primaire est composée: (role_id, user_id). Une même paire ne peut
    donc pas exister deux fois.
    """

    __tablename__ = "user_roles"

    role_id = db.Column(db.ForeignKey("roles.role_id"), primary_key=True)
    user_id = db.Column(db.ForeignKey("users.user_id"), primary_key=True)

    # back_populates relie les deux côtés: modifier User.roles met à jour
    # UserRole.user, et inversement.
    user = db.relationship('User', back_populates="roles")
    role = db.relationship('Role', back_populates="users")

    def __repr__(self):
        return f"<UserRole user={self.user_id} role={self.role_id}>"
