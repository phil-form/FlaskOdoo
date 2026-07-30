from argon2 import PasswordHasher

from app import app, db
from app.framework.seed import Seedable
from app.models.basket import Basket
from app.models.role import Role
from app.models.user import User


class UserSeed(Seedable):
    """Les comptes de démonstration.

    order = 20: après RoleSeed (10), parce qu'on attribue des rôles ici.
    """

    order = 20

    # (username, mot de passe en clair, email, description, rôles)
    USERS = [
        ("admin", "admin", "admin@example.com", "Compte administrateur de démo",
         ["USER", "ADMIN"]),
        ("test", "test", "test@example.com", "Compte utilisateur de démo",
         ["USER"]),
    ]

    def seed(self):
        hasher = PasswordHasher()

        for username, password, email, description, role_names in self.USERS:
            if User.query.filter_by(username=username).first() is not None:
                app.logger.debug(f"Seed user {username}: déjà présent")
                continue

            user = User(username=username,
                        email=email,
                        description=description,
                        # Comptes de démonstration: adresse considérée comme
                        # vérifiée, sinon /seed obligerait à passer par Mailpit
                        # avant de pouvoir tester la moindre commande.
                        email_verified=True,
                        # Jamais de mot de passe en clair en base, même pour un
                        # jeu de données de test: on prend les mêmes habitudes
                        # partout.
                        password=hasher.hash(password))

            # add() AVANT d'attribuer les rôles: sans ça, la requête
            # Role.query.filter_by(...) de la boucle déclenche un autoflush
            # alors que les UserRole créés ne sont rattachés à aucune session
            # (SQLAlchemy émet un SAWarning et n'insère pas la liaison).
            db.session.add(user)

            for role_name in role_names:
                role = Role.query.filter_by(role_name=role_name).first()

                if role is None:
                    # Ne devrait pas arriver grâce à `order`, mais un seeder ne
                    # doit pas partir du principe que la base est parfaite.
                    app.logger.warning(f"Seed user {username}: rôle {role_name} absent")
                    continue

                user.add_role(role)

            # Tout utilisateur démarre avec un panier ouvert. Comme la relation
            # User.baskets est en cascade, ce panier sera inséré avec le user.
            user.baskets.append(Basket())

            app.logger.debug(f"Seed user {username}")

        # Un seul commit pour tous les users: soit tout passe, soit rien
        # (une transaction). Le try/except est dans Seed.__seed, qui logue
        # l'erreur et continue avec les seeders suivants.
        db.session.commit()
