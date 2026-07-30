from sqlalchemy.sql import func

from app import db


class BaseEntity:
    """Colonnes techniques communes à toutes les entités (mixin).

    Ce n'est PAS un modèle: la classe n'hérite pas de db.Model et n'a donc pas
    de table. SQLAlchemy la traite comme un "mixin déclaratif": les colonnes
    déclarées ici sont recopiées dans chaque modèle qui en hérite.

        class Item(BaseEntity, db.Model):   # -> items a aussi created_at, ...

    - created_at: rempli par la base (server_default) à l'INSERT
    - updated_at: mis à jour par SQLAlchemy (onupdate) à chaque UPDATE
    - deleted_at / active: "soft delete", on marque au lieu de supprimer
      (utile pour garder l'historique, ex: un user supprimé mais ses commandes
      restent cohérentes).
    """

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    deleted_at = db.Column(db.DateTime(timezone=True))
    active = db.Column(db.Boolean, nullable=False, default=True,
                       server_default=db.true())

    def soft_delete(self):
        """Désactive l'entité sans l'effacer de la base."""
        self.active = False
        self.deleted_at = func.now()
