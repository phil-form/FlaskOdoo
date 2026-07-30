from abc import ABC, abstractmethod


class AbstractDTO(ABC):
    """Contrat commun à tous les DTO (Data Transfer Object).

    Un DTO est une photo figée d'une entité, destinée à sortir de la couche
    service: templates, JSON, session... Pourquoi ne pas passer l'entité
    directement?

    1. Une entité est attachée à la session SQLAlchemy. Si le template accède à
       `user.roles` après la fermeture de la session, on prend une
       DetachedInstanceError (ou une requête SQL surprise en pleine page).
    2. Une entité contient des champs qu'on ne veut jamais exposer
       (le hash du mot de passe...).
    3. Ça découple la vue du schéma de base: renommer une colonne ne casse pas
       tous les templates, seulement le mapper.

    Deux méthodes conventionnelles:
    - build_from_entity(entity): fabrique le DTO depuis l'entité (statique)
    - get_json_parsable(): version 100% types de base, prête pour jsonify()
    """

    @staticmethod
    @abstractmethod
    def build_from_entity(entity):
        pass

    @abstractmethod
    def get_json_parsable(self):
        pass
