from flask import Flask, render_template

from app.framework.seed.seedable import Seedable


class Seed:
    """Expose la route de seeding, qui exécute tous les Seedable enregistrés.

    Les seeders ne sont PAS découverts ici: ils s'enregistrent tout seuls à
    l'import de leur module (voir Seedable.__init_subclass__), et c'est le
    `from app.seed import *` de app/__init__.py qui provoque ces imports —
    exactement le même mécanisme que pour les modèles et les controllers.

    Cette classe ne s'occupe donc que de la route:

        seed = Seed(app)

    Et elle ne l'enregistre QUE si l'application est en debug: une URL qui
    réinjecte des données de test ne doit jamais exister en production.
    """

    def __init__(self, app: Flask, route: str = "/seed"):
        self.__app = app

        if not app.debug:
            app.logger.info(f"Seed: {route} non enregistrée (application hors debug)")
            return

        # Équivalent de @app.get(route) mais utilisable sur une méthode:
        # add_url_rule(règle, nom_du_endpoint, fonction).
        # self.__seed est une méthode liée: elle transporte son `self`.
        app.add_url_rule(route, "seed", self.__seed, methods=["GET"])

    def __seed(self):
        """La vue derrière /seed: exécute tous les seeders enregistrés."""
        seeded = []
        failed = []

        for seeder in Seedable.seeders():
            try:
                self.__app.logger.debug(f"Seeding {seeder.__name__}")
                seeder().seed()
                seeded.append(seeder.__name__)
            except Exception as e:
                # Un seeder en erreur ne doit pas empêcher les suivants.
                self.__app.logger.error(f"{seeder.__name__}: {e}")
                failed.append(f"{seeder.__name__} ({e})")

        return render_template('seed/seed.html',
                               seeded=seeded,
                               failed=failed)
