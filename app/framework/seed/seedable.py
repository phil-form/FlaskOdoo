from abc import ABC, abstractmethod


class Seedable(ABC):
    """Classe de base de tous les seeders.

    Chaque classe concrète qui hérite de Seedable s'enregistre automatiquement,
    il suffit donc d'importer son module pour qu'elle fasse partie du seeding.

    Pour écrire un seeder:

        class MonSeed(Seedable):
            order = 10          # optionnel: ordre d'exécution

            def seed(self):
                ...

    Rien d'autre à faire: pas d'import à ajouter quelque part, pas de liste à
    maintenir. Le fichier doit juste se trouver dans le package app/seed.
    """

    # Ordre d'exécution: les seeders sont triés par order croissant.
    # Utile parce que certaines données dépendent d'autres (les users ont
    # besoin des roles, les paniers ont besoin des items...).
    order: int = 100

    # Registre de toutes les classes de seed.
    # Clé = "module.Classe" pour éviter les doublons si un module est réimporté.
    __seeders: dict[str, type["Seedable"]] = {}

    def __init_subclass__(cls, **kwargs):
        """Appelé automatiquement par Python à la création d'une sous-classe.

        C'est le "hook" qui rend l'auto-enregistrement possible: dès que
        `class MonSeed(Seedable)` est lue par l'interpréteur, cette méthode est
        exécutée avec cls = MonSeed.
        """
        super().__init_subclass__(**kwargs)

        # Une sous-classe qui n'implémente pas seed() reste abstraite
        # (seed garde son marqueur __isabstractmethod__): ce n'est pas un
        # seeder exécutable, on ne l'enregistre pas.
        if getattr(cls.seed, "__isabstractmethod__", False):
            return

        Seedable.__seeders[f"{cls.__module__}.{cls.__qualname__}"] = cls

    @staticmethod
    def seeders() -> list[type["Seedable"]]:
        """Toutes les classes de seed enregistrées, triées par `order`."""
        return sorted(Seedable.__seeders.values(), key=lambda seeder: seeder.order)

    @abstractmethod
    def seed(self):
        """Insère les données. À implémenter dans chaque seeder."""
        pass
