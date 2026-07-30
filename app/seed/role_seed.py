from app import app, db
from app.framework.seed import Seedable
from app.models.role import Role


class RoleSeed(Seedable):
    """Les rôles de l'application.

    order = 10: ce seeder passe avant tous les autres (order par défaut = 100),
    parce que UserSeed a besoin des rôles pour les attribuer.
    """

    order = 10

    ROLES = ["USER", "ADMIN"]

    def seed(self):
        for role_name in self.ROLES:
            # Idempotence: on ne recrée pas ce qui existe déjà. Sans ce test,
            # un deuxième appel à /seed violerait la contrainte unique sur
            # role_name et ferait échouer tout le seeding.
            if Role.query.filter_by(role_name=role_name).first() is not None:
                continue

            app.logger.debug(f"Seed role {role_name}")
            db.session.add(Role(role_name=role_name))

        db.session.commit()
