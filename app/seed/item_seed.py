from app import app, db
from app.framework.seed import Seedable
from app.models.item import Item


class ItemSeed(Seedable):
    """Le catalogue de démonstration.

    order = 30: après les users, avant les paniers (BasketSeed, 40).
    Aucune dépendance réelle avec les users, mais garder un ordre lisible
    (10, 20, 30...) permet d'insérer un seeder entre deux sans tout renuméroter.
    """

    order = 30

    ITEMS = [
        ("Clavier mécanique", "Switches bleus, ISO-BE, rétroéclairage blanc.", 12),
        ("Souris ergonomique", "Capteur 16000 dpi, 6 boutons programmables.", 30),
        ("Écran 27\"", "Dalle IPS 2560x1440, 144 Hz, pied réglable.", 7),
        ("Casque USB", "Réduction de bruit, micro sur perche.", 25),
        ("Station d'accueil", "USB-C, 2x HDMI, RJ45, 100 W passthrough.", 5),
        ("Webcam 1080p", "Autofocus, cache de confidentialité.", 0),
    ]

    def seed(self):
        for name, description, stock in self.ITEMS:
            if Item.query.filter_by(name=name).first() is not None:
                continue

            app.logger.debug(f"Seed item {name}")
            db.session.add(Item(name=name, description=description, stock=stock))

        db.session.commit()
