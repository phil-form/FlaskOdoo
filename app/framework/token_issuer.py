from abc import ABC, abstractmethod


class TokenIssuer(ABC):
    """Émettre et lire un token d'accès. Interface séparée d'AuthService.

    Pourquoi une deuxième interface, alors qu'`AuthServiceJwt` implémente déjà
    les deux?

    Parce qu'elles répondent à des questions différentes:

    - `AuthService` répond « qui est connecté sur CETTE requête? ». C'est ce
      dont un controller MVC a besoin, et ça marche avec une session comme avec
      un token — c'est bien pour ça que l'étape 14 a pu remplacer l'un par
      l'autre sans toucher un seul controller;
    - `TokenIssuer` répond « fabrique-moi un token pour ce compte ». Seule une
      API en a besoin, et ça n'a de sens QUE pour une implémentation à base de
      tokens: `AuthServiceImpl` (session) ne saurait pas quoi en faire.

    Les fusionner obligerait `AuthServiceImpl` à implémenter des méthodes qui
    n'ont aucun sens pour elle — c'est la définition d'une interface trop
    grosse. Les séparer laisse chaque implémentation ne signer que ce qu'elle
    sait faire.

    L'injecteur accepte les deux enregistrements sur la même classe:

        @injectable(base=AuthService, scope=Scope.SCOPED)
        @injectable(base=TokenIssuer, scope=Scope.SCOPED)
        class AuthServiceJwt(AuthService, TokenIssuer):

    Ça fonctionne parce que `@injectable` retourne la classe **inchangée**: les
    deux décorateurs se contentent d'ajouter une ligne au registre, l'un sous
    'AuthService', l'autre sous 'TokenIssuer'. Un controller demande l'une ou
    l'autre selon ce dont il a besoin, et reçoit la même instance (scope
    SCOPED: une par requête).
    """

    @abstractmethod
    def encode(self, user, famille: str | None = None) -> str:
        """Un token d'accès signé pour cet utilisateur.

        `famille` est l'identifiant de la famille de refresh tokens à laquelle
        ce token appartient (claim `fam`, étape 15). Il est optionnel parce
        qu'il ne sert qu'au parcours navigateur: la déconnexion s'y fait sans
        jamais voir le refresh token, confiné à `/auth/refresh`. Un client
        d'API, lui, détient le sien et le présente pour le révoquer — il n'a
        rien à retrouver.
        """

    @abstractmethod
    def decode(self, token: str) -> dict | None:
        """Les claims du token, ou None s'il est invalide ou expiré."""
