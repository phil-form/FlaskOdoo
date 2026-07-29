from argon2 import PasswordHasher

from app import app, db
from app.framework.seed import Seedable
from app.models.user import User


class UserSeed(Seedable):
    """Les comptes de démonstration.

    `order` fixe l'ordre d'exécution entre seeders (10, 20, 30... pour pouvoir
    en insérer un entre deux sans tout renuméroter). Ici il n'y en a qu'un.
    """

    order = 20

    # (username, mot de passe en clair)
    USERS = [
        ("admin", "admin"),
        ("test", "test"),
    ]

    def seed(self):
        hasher = PasswordHasher()

        for username, password in self.USERS:
            # Idempotence: relancer /seed ne doit pas violer la contrainte
            # unique sur username.
            if User.query.filter_by(username=username).first() is not None:
                app.logger.debug(f"Seed user {username}: déjà présent")
                continue

            app.logger.debug(f"Seed user {username}")
            # Jamais de mot de passe en clair en base, même pour un jeu de
            # données de test: on prend les mêmes habitudes partout.
            db.session.add(User(username=username,
                                password=hasher.hash(password)))

        db.session.commit()
