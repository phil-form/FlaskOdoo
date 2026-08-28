import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from app import app, db
from app.framework.decorators.injectable import injectable
from app.models.refresh_token import RefreshToken


@injectable
class RefreshTokenService:
    """Émission, rotation et révocation des refresh tokens.

    Le cycle de vie complet:

        connexion    -> émission d'un token (nouvelle famille)
        access expiré -> rotation: l'ancien est marqué consommé, un nouveau est
                         émis dans la même famille
        déconnexion  -> révocation de toute la famille
        rejeu détecté -> révocation de toute la famille (voir plus bas)

    **La détection de rejeu**, le point le plus intéressant. Si un token déjà
    consommé est présenté à nouveau, il y a deux explications:

    1. un client maladroit (deux onglets qui rafraîchissent en même temps);
    2. un token volé — l'attaquant utilise sa copie, ou la victime utilise la
       sienne après l'attaquant.

    On ne peut pas distinguer les deux, alors on choisit la sécurité: on révoque
    la famille entière. Le vrai utilisateur devra se reconnecter, l'attaquant
    aussi — et lui ne peut pas.
    """

    def __init__(self):
        self.__days = int(os.environ.get("JWT_REFRESH_DAYS", 7))

    # --- utilitaires --------------------------------------------------------

    @staticmethod
    def __hash(token: str) -> str:
        # Le token fait déjà 32 octets aléatoires: pas besoin d'argon2 ici, il n'y
        # a rien à « deviner ». On hashe pour qu'une fuite de la table ne donne
        # pas de tokens utilisables.
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def __find(self, token: str) -> RefreshToken | None:
        return RefreshToken.query.filter_by(token_hash=self.__hash(token)).first()

    # --- émission ----------------------------------------------------------

    def issue(self, user_id: int, family_id: str | None = None) -> str | None:
        """Crée un refresh token et retourne sa valeur EN CLAIR (une seule fois).

        C'est le même principe qu'une clé d'API: la valeur n'est connue qu'à
        l'émission, la base n'en garde que l'empreinte.
        """
        # token_urlsafe(32) = 32 octets d'entropie, pas 32 caractères. Le module
        # `secrets` (et non `random`) est le seul acceptable pour du secret.
        token = secrets.token_urlsafe(32)

        ligne = RefreshToken(
            token_hash=self.__hash(token),
            user_id=user_id,
            family_id=family_id or secrets.token_hex(16),
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.__days))

        try:
            db.session.add(ligne)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"issue refresh: {e}")
            db.session.rollback()
            return None

        return token

    # --- rotation ----------------------------------------------------------

    def rotate(self, token: str) -> tuple[int, str, str] | None:
        """Consomme un token et en émet un nouveau.

        Retourne `(user_id, nouveau_token, family_id)`, ou None si le token est
        inconnu, expiré, ou déjà consommé — et dans ce dernier cas, révoque
        toute la famille.

        Le `family_id` fait partie du retour parce que l'appelant en a besoin
        pour le claim `fam` du nouvel access token: la rotation reste dans la
        MÊME famille, et c'est elle que la déconnexion révoquera.
        """
        ligne = self.__find(token)

        if ligne is None:
            app.logger.warning("refresh: token inconnu")
            return None

        if ligne.revoked_at is not None:
            # REJEU. Soit un vol, soit deux onglets. On tranche pour la sécurité.
            app.logger.warning(
                f"refresh: REJEU détecté (user {ligne.user_id}), "
                f"révocation de la famille {ligne.family_id[:8]}")
            self.revoke_family(ligne.family_id)
            return None

        if not ligne.is_usable():
            app.logger.info("refresh: token expiré")
            return None

        ligne.revoked_at = datetime.now(timezone.utc)

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"rotate refresh: {e}")
            db.session.rollback()
            return None

        nouveau = self.issue(ligne.user_id, family_id=ligne.family_id)

        return (ligne.user_id, nouveau, ligne.family_id) if nouveau else None

    # --- révocation --------------------------------------------------------

    def revoke(self, token: str):
        ligne = self.__find(token)

        if ligne is None or ligne.revoked_at is not None:
            return

        ligne.revoked_at = datetime.now(timezone.utc)
        self.__commit()

    def revoke_family(self, family_id: str):
        RefreshToken.query.filter_by(family_id=family_id, revoked_at=None).update(
            {'revoked_at': datetime.now(timezone.utc)})
        self.__commit()

    def revoke_all_for_user(self, user_id: int):
        """Déconnecte l'utilisateur de PARTOUT.

        C'est ce qu'il faut appeler après un changement de mot de passe: sinon un
        attaquant qui possède un refresh token garde l'accès malgré le changement.
        """
        RefreshToken.query.filter_by(user_id=user_id, revoked_at=None).update(
            {'revoked_at': datetime.now(timezone.utc)})
        self.__commit()

    def purge_expired(self) -> int:
        """Ménage: à appeler par une tâche planifiée. Rien ne le fait ici."""
        supprimes = RefreshToken.query.filter(
            RefreshToken.expires_at < datetime.now(timezone.utc)).delete()
        self.__commit()

        return supprimes

    def __commit(self):
        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"refresh token: {e}")
            db.session.rollback()
