import os
import smtplib
from email.message import EmailMessage

from app import app
from app.framework.decorators.injectable import injectable


@injectable
class MailService:
    """Envoi de mails via SMTP.

    Pas de dépendance supplémentaire: `smtplib` et `email.message` sont dans la
    bibliothèque standard. Flask-Mail ferait la même chose avec plus de confort,
    mais aussi plus de magie — ici on voit le protocole.

    En développement, le destinataire est Mailpit (docker-compose): il accepte
    tout, n'envoie rien, et affiche les mails sur http://localhost:8025
    C'est LA bonne façon de travailler sur des envois: aucun risque d'écrire
    réellement à quelqu'un, et on relit le contenu exact reçu.

    Ce service ne fait pas partie du CRUD (il n'hérite donc pas de BaseService et
    ne touche pas à la base), mais il est injectable comme les autres.
    """

    def __init__(self):
        self.__host = os.environ.get("MAIL_HOST", "127.0.0.1")
        self.__port = int(os.environ.get("MAIL_PORT", 1025))
        self.__sender = os.environ.get("MAIL_FROM", "no-reply@flaskodoo.local")
        self.__use_tls = os.environ.get("MAIL_USE_TLS", "False").lower() in ("1", "true", "yes")
        # `or None`: une variable vide dans le .env doit être lue comme "absente"
        self.__username = os.environ.get("MAIL_USERNAME") or None
        self.__password = os.environ.get("MAIL_PASSWORD") or None

    def send(self, to: str, subject: str, body: str) -> bool:
        """Envoie un mail texte. Retourne False en cas d'échec, sans lever.

        Pourquoi ne pas laisser l'exception remonter? Parce qu'un serveur SMTP
        indisponible ne doit pas transformer une page en erreur 500: l'appelant
        décide quoi dire à l'utilisateur.
        """
        message = EmailMessage()
        message['From'] = self.__sender
        message['To'] = to
        message['Subject'] = subject
        # set_content encode le corps et pose les bons en-têtes (charset, MIME).
        message.set_content(body)

        try:
            # timeout: sans lui, un serveur qui ne répond pas bloque la requête
            # HTTP jusqu'à l'infini.
            with smtplib.SMTP(self.__host, self.__port, timeout=5) as smtp:
                if self.__use_tls:
                    # STARTTLS chiffre la connexion. Mailpit n'en a pas besoin
                    # (tout est local), un vrai serveur SMTP l'exige.
                    smtp.starttls()

                if self.__username and self.__password:
                    smtp.login(self.__username, self.__password)

                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as e:
            app.logger.error(f"mail vers {to} non envoyé: {e}")
            return False

        app.logger.debug(f"mail envoyé à {to}: {subject}")

        return True
