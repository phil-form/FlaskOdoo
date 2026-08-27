from datetime import datetime, timezone

from app import db
from app.models.base_entity import BaseEntity


class RefreshToken(BaseEntity, db.Model):
    """Un refresh token, côté serveur.

    Pourquoi une table, alors que tout l'intérêt du JWT est d'être sans état ?

    Parce que les deux tokens n'ont pas le même rôle:

    - l'**access token** est court (quelques minutes) et sans état: on l'accepte
      sur sa seule signature, sans rien vérifier en base. C'est lui qui rend
      l'autorisation rapide.
    - le **refresh token** est long (des jours) et doit pouvoir être RÉVOQUÉ:
      déconnexion, changement de mot de passe, vol détecté. Un token long qu'on
      ne peut pas révoquer, c'est un mot de passe qui ne change jamais.

    Ce qui est stocké: un **hash** du token, jamais sa valeur. Même raisonnement
    que pour les mots de passe: une fuite de la table ne doit pas donner des
    sessions utilisables. Ici un sha256 simple suffit (le token est déjà 32 octets
    aléatoires, il n'y a rien à « deviner » par force brute).

    `family_id` regroupe tous les tokens issus d'une même connexion. La rotation
    remplace un token par le suivant dans la même famille; si un token déjà
    utilisé revient, on révoque **toute la famille** (voir RefreshTokenService).
    """

    __tablename__ = "refresh_tokens"

    refresh_token_id = db.Column(db.Integer, primary_key=True)
    # sha256 hexadécimal = 64 caractères
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    user_id = db.Column(db.ForeignKey('users.user_id'), nullable=False, index=True)
    # Identifiant de la lignée de tokens (une connexion = une famille)
    family_id = db.Column(db.String(64), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    # Rempli quand le token est consommé (rotation) ou révoqué
    revoked_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship('User')

    @staticmethod
    def en_utc(valeur: datetime | None) -> datetime | None:
        """PostgreSQL rend un datetime aware, SQLite un datetime naïf: on aligne.

        Même utilitaire que LoginAttempt — c'est le prix de la portabilité entre
        les deux bases.
        """
        if valeur is None:
            return None

        return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=timezone.utc)

    def is_usable(self) -> bool:
        if self.revoked_at is not None:
            return False

        return self.en_utc(self.expires_at) > datetime.now(timezone.utc)

    def __repr__(self):
        return f"<RefreshToken user={self.user_id} famille={self.family_id[:8]}>"
