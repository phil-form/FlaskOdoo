from flask_sqlalchemy import SQLAlchemy

from app.framework.seedable import Seedable
from app.models.user import User
from argon2 import PasswordHasher
from app import db, app


class UserSeed(Seedable):
    def seed(self):
        ph = PasswordHasher()
        users = [
            User(username="admin", password=ph.hash("admin")),
            User(username="test", password=ph.hash("test")),
        ]

        try:
            for user in users:
                app.logger.debug("Add user")
                db.session.add(user)

            db.session.commit()
        except Exception as e:
            app.logger.error(e)
