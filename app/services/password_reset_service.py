import hashlib
import os
from secrets import compare_digest

from flask import render_template, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import app
from app.dtos.user_dto import UserDTO
from app.framework.decorators.inject import inject
from app.framework.decorators.injectable import injectable
from app.mappers.user_mapper import UserMapper
from app.services.mail_service import MailService
from app.services.user_service import UserService


@injectable
class PasswordResetService:
    """Réinitialisation de mot de passe par lien envoyé par mail.

    Le lien contient un token SIGNÉ, pas d'identifiant en clair. Aucune table
    supplémentaire n'est nécessaire: tout ce dont on a besoin est dans le token,
    et sa signature (faite avec SECRET_KEY) garantit qu'il n'a pas été fabriqué
    ni modifié par le client. C'est `itsdangerous`, la bibliothèque qui signe
    déjà les cookies de session de Flask — elle est donc déjà installée.

    Trois protections, à comprendre ensemble:

    1. **Signature** — un token modifié est rejeté (BadSignature).
    2. **Expiration** — URLSafeTimedSerializer horodate le token, `max_age`
       le refuse au-delà de PASSWORD_RESET_MAX_AGE (1h par défaut).
    3. **Usage unique** — le token embarque une empreinte du hash de mot de passe
       courant. Dès que le mot de passe change, l'empreinte ne correspond plus et
       le lien devient inutilisable. Sans ça, un lien resté dans une boîte mail
       permettrait de reprendre le compte pendant toute la durée de validité.

    Le `salt` sépare les usages: un token de réinitialisation ne pourra jamais
    être accepté là où on attend un autre type de token signé, même clé secrète.
    """

    SALT = 'password-reset'

    @inject
    def __init__(self, user_service: UserService, mail_service: MailService):
        self.__user_service = user_service
        self.__mail_service = mail_service
        self.__max_age = int(os.environ.get("PASSWORD_RESET_MAX_AGE", 3600))
        self.__serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'],
                                                   salt=self.SALT)

    # --- envoi --------------------------------------------------------------

    def send_reset_link(self, email: str) -> bool:
        """Envoie le lien si un compte actif correspond à cette adresse.

        Retourne False si l'adresse est inconnue — mais le controller répond la
        même chose dans les deux cas, pour ne pas révéler qui a un compte.
        """
        user = self.__user_service.find_one_by(email=email, active=True)

        if user is None:
            app.logger.info(f"reset: aucune adresse {email}")
            return False

        token = self.__serializer.dumps({
            'user_id': user.user_id,
            'fingerprint': self.__fingerprint(user.password),
        })

        # _external=True: une URL absolue (http://host/...), indispensable dans
        # un mail — un lien relatif n'y veut rien dire.
        link = url_for('password_reset', token=token, _external=True)

        body = render_template('emails/password_reset.txt',
                               username=user.username,
                               link=link,
                               minutes=self.__max_age // 60)

        return self.__mail_service.send(
            user.email, "Réinitialisation de votre mot de passe", body)

    # --- vérification / application -----------------------------------------

    def find_user(self, token: str) -> UserDTO | None:
        """Le user derrière un token valide, sinon None (DTO, pour la vue)."""
        user = self.__find_user_entity(token)

        return UserMapper.entity_to_dto(user) if user else None

    def reset(self, token: str, new_password: str) -> bool:
        """Applique le nouveau mot de passe. Revalide le token au passage.

        Le token est revérifié ici et pas seulement à l'affichage du formulaire:
        entre le GET et le POST, il a pu expirer ou être déjà consommé.
        """
        user = self.__find_user_entity(token)

        if user is None:
            return False

        return self.__user_service.update_password(user.user_id, new_password) is not None

    # --- interne ------------------------------------------------------------

    def __find_user_entity(self, token: str):
        try:
            data = self.__serializer.loads(token, max_age=self.__max_age)
        except SignatureExpired:
            app.logger.info("reset: token expiré")
            return None
        except BadSignature:
            # Token tronqué, bricolé, ou signé avec une autre SECRET_KEY.
            app.logger.warning("reset: token invalide")
            return None

        user = self.__user_service.find_one_entity(data.get('user_id'))

        if user is None or not user.active:
            return None

        # compare_digest au lieu de ==: comparaison à temps constant, elle ne
        # laisse pas deviner l'empreinte attendue caractère par caractère.
        if not compare_digest(data.get('fingerprint', ''),
                              self.__fingerprint(user.password)):
            app.logger.info("reset: token déjà utilisé (mot de passe modifié)")
            return None

        return user

    @staticmethod
    def __fingerprint(password_hash: str) -> str:
        """Empreinte courte du hash de mot de passe.

        On ne met évidemment PAS le hash lui-même dans le token: il circulerait
        dans une URL et dans une boîte mail. Un sha256 tronqué suffit à détecter
        un changement de mot de passe, et ne permet pas de remonter au hash.
        """
        return hashlib.sha256(password_hash.encode('utf-8')).hexdigest()[:16]
