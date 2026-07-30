from app import db
from app.models.base_entity import BaseEntity


class Role(BaseEntity, db.Model):
    """Un rôle applicatif ("USER", "ADMIN").

    Relation many-to-many avec User, matérialisée par la table d'association
    UserRole (voir app/models/user_role.py).
    """

    __tablename__ = "roles"

    role_id = db.Column(db.Integer, primary_key=True)
    # index=True: on cherche souvent un rôle par son nom (seeds, contrôles)
    role_name = db.Column(db.String(50), nullable=False, unique=True, index=True)

    # Côté "many" de la relation: les lignes de la table d'association.
    users = db.relationship('UserRole', back_populates='role')

    def __repr__(self):
        return f"<Role {self.role_name}>"
