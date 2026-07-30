from abc import ABC, abstractmethod

from app.dtos.user_dto import UserDTO


class AuthService(ABC):
    """Qui est connecté? Interface volontairement minuscule.

    Pourquoi une interface abstraite alors qu'il n'y a qu'une implémentation
    (AuthServiceImpl)? Parce que c'est le point de variation du projet: on
    stocke aujourd'hui l'identité dans la session Flask (site web classique),
    on pourrait demain la lire dans un token JWT (API) sans toucher une seule
    ligne des controllers.

    C'est aussi ce que montre le décorateur posé sur l'implémentation:
        @injectable(base=AuthService, scope=Scope.SCOPED)
        class AuthServiceImpl(AuthService): ...
    Les controllers demandent AuthService, l'injecteur décide quoi livrer.
    """

    @abstractmethod
    def get_current_user(self) -> UserDTO | None:
        """Le user connecté, ou None si visiteur anonyme."""

    @abstractmethod
    def login(self, user: UserDTO):
        """Marque l'utilisateur comme connecté."""

    @abstractmethod
    def logout(self):
        """Termine la session."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        pass
