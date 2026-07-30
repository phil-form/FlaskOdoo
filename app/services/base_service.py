from abc import ABC, abstractmethod


class BaseService(ABC):
    """Contrat CRUD commun à tous les services.

    Le service est la seule couche qui parle à la base (`db.session`). Les
    controllers ne font jamais de requête eux-mêmes: ils appellent un service.
    Résultat: la logique est testable sans HTTP, et réutilisable depuis un
    seed, une commande CLI ou un autre service.

    Convention de retour: un service renvoie des DTO, pas des entités
    (sauf les méthodes explicitement nommées `*_entity`, réservées aux appels
    internes entre services).
    """

    @abstractmethod
    def find_all(self):
        """Toutes les entités (sous forme de DTO)."""

    @abstractmethod
    def find_one(self, entity_id: int):
        """Une entité par sa clé primaire, ou None."""

    @abstractmethod
    def find_one_by(self, **kwargs):
        """Une entité par n'importe quelle colonne: find_one_by(username='x')."""

    @abstractmethod
    def insert(self, data):
        """Crée une entité à partir d'un formulaire validé."""

    @abstractmethod
    def update(self, entity_id: int, data):
        """Met à jour une entité existante."""

    @abstractmethod
    def delete(self, entity_id: int):
        """Supprime une entité."""
