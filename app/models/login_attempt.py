from datetime import datetime, timedelta, timezone

from app import db
from app.models.base_entity import BaseEntity


class LoginAttempt(BaseEntity, db.Model):
    """Compteur d'échecs de connexion, par identifiant.

    Pourquoi une table et pas un dictionnaire en mémoire ?

    - un dictionnaire est perdu au redémarrage: il suffit d'attendre un déploiement
      pour repartir à zéro;
    - il n'est pas partagé entre les processus: avec 4 workers gunicorn, un
      attaquant a droit à 4 fois plus d'essais;
    - il grossit indéfiniment si personne ne le nettoie.

    Une table règle les trois. Le prix: deux requêtes SQL par tentative de
    connexion. À l'échelle d'un login, c'est négligeable — et si ça ne l'était
    plus, on passerait à Redis (voir les exercices).
    """

    __tablename__ = "login_attempts"

    login_attempt_id = db.Column(db.Integer, primary_key=True)
    # L'identifiant SAISI, pas l'utilisateur trouvé: on doit pouvoir compter les
    # essais sur un compte qui n'existe pas (sinon il suffit de se tromper de nom
    # une fois sur deux pour ne jamais être bloqué).
    identifier = db.Column(db.String(120), nullable=False, unique=True, index=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    last_attempt_at = db.Column(db.DateTime(timezone=True))

    @staticmethod
    def en_utc(valeur: datetime | None) -> datetime | None:
        """Rend un datetime comparable, qu'il vienne de PostgreSQL ou de SQLite.

        Piège de portabilité: avec `DateTime(timezone=True)`, PostgreSQL rend un
        datetime **aware** (il connaît son décalage), SQLite un datetime
        **naïf** (il n'a pas de type date, il stocke du texte). Comparer les deux
        lève `TypeError: can't compare offset-naive and offset-aware datetimes`.

        On considère donc qu'un datetime naïf lu en base est de l'UTC — ce qui est
        vrai ici, puisque tout ce qu'on écrit est en UTC.
        """
        if valeur is None:
            return None

        return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=timezone.utc)

    def is_locked(self) -> bool:
        locked_until = self.en_utc(self.locked_until)

        if locked_until is None:
            return False

        return locked_until > datetime.now(timezone.utc)

    def remaining_seconds(self) -> int:
        if not self.is_locked():
            return 0

        return int((self.en_utc(self.locked_until)
                    - datetime.now(timezone.utc)).total_seconds())

    def __repr__(self):
        return f"<LoginAttempt {self.identifier} {self.failures} échec(s)>"
