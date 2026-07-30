import os

from flask import render_template, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import app
from app.framework.decorators.inject import inject
from app.framework.decorators.injectable import injectable
from app.services.mail_service import MailService
from app.services.user_service import UserService


@injectable
class EmailVerificationService:
    """Vérification de l'adresse email fournie à l'inscription.

    Même mécanisme que la réinitialisation de mot de passe (token signé par
    `itsdangerous`, aucune table supplémentaire), avec deux différences qui
    méritent d'être comprises:

    1. **Un autre `salt`.** `salt='email-verification'` produit des signatures
       incompatibles avec `salt='password-reset'`. Un lien de vérification ne
       pourra donc jamais être présenté à `/password/reset/<token>` pour
       reprendre un compte — alors que la clé secrète est la même. Séparer les
       usages est la règle: un token = un usage.

    2. **L'usage unique vient de l'effet lui-même.** Le token embarque l'adresse
       vérifiée; on refuse le token si l'adresse a changé ou si le compte est
       déjà vérifié. Pas besoin d'empreinte du mot de passe comme pour la
       réinitialisation.

    La durée de vie est plus longue (24h par défaut): un mail d'inscription peut
    dormir une nuit dans une boîte, alors qu'un lien de réinitialisation doit
    être court.
    """

    SALT = 'email-verification'

    @inject
    def __init__(self, user_service: UserService, mail_service: MailService):
        self.__user_service = user_service
        self.__mail_service = mail_service
        self.__max_age = int(os.environ.get("EMAIL_VERIFICATION_MAX_AGE", 86400))
        self.__serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'],
                                                   salt=self.SALT)

    # --- envoi --------------------------------------------------------------

    def send_verification_link(self, user_id: int) -> bool:
        """Envoie (ou renvoie) le lien de vérification."""
        user = self.__user_service.find_one_entity(user_id)

        if user is None or user.email_verified:
            # Déjà vérifié: ne rien envoyer. Et surtout ne pas le dire
            # différemment à l'appelant côté HTTP (voir le controller).
            return False

        token = self.__serializer.dumps({'user_id': user.user_id,
                                         'email': user.email})

        link = url_for('email_verify', token=token, _external=True)

        body = render_template('emails/email_verification.txt',
                               username=user.username,
                               link=link,
                               hours=self.__max_age // 3600)

        return self.__mail_service.send(
            user.email, "Confirmez votre adresse email", body)

    # --- vérification -------------------------------------------------------

    def verify(self, token: str) -> bool:
        """Marque l'adresse comme vérifiée si le token est valide."""
        try:
            data = self.__serializer.loads(token, max_age=self.__max_age)
        except SignatureExpired:
            app.logger.info("vérification email: token expiré")
            return False
        except BadSignature:
            # Token bricolé, tronqué, ou signé avec un autre salt (celui de la
            # réinitialisation de mot de passe, par exemple).
            app.logger.warning("vérification email: token invalide")
            return False

        user = self.__user_service.find_one_entity(data.get('user_id'))

        if user is None or not user.active:
            return False

        # L'adresse a changé depuis l'envoi: le lien ne vaut plus rien.
        if user.email != data.get('email'):
            app.logger.info("vérification email: l'adresse a changé")
            return False

        # Déjà vérifié: le lien a donc déjà servi (usage unique).
        if user.email_verified:
            return False

        return self.__user_service.mark_email_verified(user.user_id) is not None
