import os
from datetime import datetime, timedelta, timezone

from app import app, db
from app.framework.decorators.injectable import injectable
from app.models.login_attempt import LoginAttempt


@injectable
class LoginAttemptService:
    """Verrouillage temporaire d'un compte après trop d'échecs de connexion.

    Sans ça, rien n'empêche d'essayer des mots de passe en boucle: argon2 rend
    chaque essai coûteux (~50 ms), mais 50 ms x 24 h = ~1,7 million d'essais.
    C'est très suffisant pour trouver « été2024 ».

    Règle appliquée: MAX_FAILURES échecs consécutifs -> compte bloqué pendant
    LOCK_MINUTES minutes. Une connexion réussie remet le compteur à zéro.

    Deux principes à respecter, et ils se contredisent en apparence:

    1. **Ne pas renseigner l'attaquant.** Le message affiché ne dit pas si le
       compte existe. Mais il DOIT dire que c'est temporairement bloqué, sinon
       l'utilisateur légitime avec le bon mot de passe ne comprend rien.
       Compromis retenu: « trop de tentatives, réessayez dans N minutes », affiché
       pour un identifiant existant comme inexistant.
    2. **Ne pas se faire bloquer son propre compte par un tiers.** Un attaquant
       peut volontairement échouer 5 fois pour vous verrouiller: c'est un déni de
       service ciblé. C'est le défaut connu de cette approche, et la raison pour
       laquelle les gros services combinent compteur par compte ET par IP,
       captcha, et 2FA. Voir les exercices.
    """

    MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", 5))
    LOCK_MINUTES = int(os.environ.get("LOGIN_LOCK_MINUTES", 15))
    # Au-delà de ce délai sans échec, on repart de zéro: 3 fautes de frappe
    # étalées sur une semaine ne doivent pas verrouiller un compte.
    RESET_MINUTES = int(os.environ.get("LOGIN_RESET_MINUTES", 60))

    def __normalize(self, identifier: str) -> str:
        # "Admin", "ADMIN" et "admin " sont le même compte pour le compteur.
        return (identifier or "").strip().lower()[:120]

    def __find(self, identifier: str) -> LoginAttempt | None:
        return LoginAttempt.query.filter_by(
            identifier=self.__normalize(identifier)).first()

    # --- lecture ------------------------------------------------------------

    def locked_seconds(self, identifier: str) -> int:
        """Secondes de blocage restantes (0 si le compte n'est pas bloqué)."""
        attempt = self.__find(identifier)

        return attempt.remaining_seconds() if attempt else 0

    # --- écriture -----------------------------------------------------------

    def record_failure(self, identifier: str) -> int:
        """Enregistre un échec. Retourne le nombre d'échecs consécutifs."""
        now = datetime.now(timezone.utc)
        attempt = self.__find(identifier)

        if attempt is None:
            attempt = LoginAttempt(identifier=self.__normalize(identifier),
                                   failures=0)
            db.session.add(attempt)
        elif (attempt.last_attempt_at is not None
              and LoginAttempt.en_utc(attempt.last_attempt_at)
                  < now - timedelta(minutes=self.RESET_MINUTES)):
            # Trop vieux: ce n'est plus une série d'échecs.
            attempt.failures = 0

        attempt.failures += 1
        attempt.last_attempt_at = now

        if attempt.failures >= self.MAX_FAILURES:
            attempt.locked_until = now + timedelta(minutes=self.LOCK_MINUTES)
            app.logger.warning(
                f"login: {attempt.identifier} bloqué {self.LOCK_MINUTES} min "
                f"après {attempt.failures} échecs")

        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f"record_failure: {e}")
            db.session.rollback()

        return attempt.failures

    def record_success(self, identifier: str):
        """Connexion réussie: on efface l'ardoise."""
        attempt = self.__find(identifier)

        if attempt is None:
            return

        try:
            db.session.delete(attempt)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"record_success: {e}")
            db.session.rollback()
