from enum import Enum

from flask import Flask, g, has_app_context


class Scope(Enum):
    """Durée de vie d'une dépendance."""

    # Il n'existe qu'une instance dans toute l'application.
    SINGLETON = 1
    # Une instance par requête HTTP (recréée à chaque requête).
    SCOPED = 2
    # Chaque appel crée une nouvelle instance.
    TRANSIENT = 3


class DependencyConfig:
    """Une ligne de configuration: "quand on demande `base`, donne `implement`".

    - base: le type demandé (souvent une classe abstraite / interface)
    - implement: la classe réellement instanciée
    - scope: sa durée de vie
    """

    def __init__(self, base, implement, scope: Scope):
        self.base = base
        self.implement = implement
        self.scope = scope


class ContainerConfig:
    """Le catalogue des dépendances, indexé par nom de classe."""

    def __init__(self):
        self.__config = {}

    def bind(self, dependency: DependencyConfig):
        self.__config[dependency.base.__name__] = dependency

    def get(self, dep_name) -> DependencyConfig | None:
        return self.__config.get(dep_name)


# --- registre global, rempli par le décorateur @injectable ------------------
# Même principe que Seedable pour les seeds: une classe s'inscrit toute seule au
# moment où Python lit sa déclaration. Il n'y a donc plus de fichier de
# configuration à tenir à jour (l'ancien injector_config.py).
#
# Clé = nom de la classe DEMANDÉE (`base`). Pour AuthService -> AuthServiceImpl,
# la clé est donc 'AuthService', puisque c'est ce que les vues demandent.
__dependencies: dict[str, DependencyConfig] = {}


def register_dependency(dependency: DependencyConfig):
    """Ajoute (ou remplace) une dépendance dans le registre global."""
    __dependencies[dependency.base.__name__] = dependency


def registered_dependencies() -> list[DependencyConfig]:
    """Toutes les dépendances déclarées par @injectable."""
    return list(__dependencies.values())


class Injector:
    """Conteneur d'injection de dépendances minimaliste.

    Utilisation:
        injector = Injector(app)
        user_service = app.injector['UserService']

    En pratique on ne l'appelle pas à la main: le décorateur @inject
    (app/framework/decorators/inject.py) lit les annotations de type de la
    fonction et va chercher les instances ici.

    Pourquoi faire ça? Les controllers ne construisent plus leurs services
    eux-mêmes (`UserService()`), ils déclarent ce dont ils ont besoin. On peut
    donc changer l'implémentation (ex: AuthService -> AuthServiceImpl) ou la
    remplacer par un mock dans les tests, sans toucher aux controllers.

    Le catalogue est constitué par le décorateur @injectable posé sur les
    services: l'injecteur ne fait que recopier le registre global rempli à
    l'import. Il faut donc que les modules de services soient importés AVANT
    de créer l'injecteur (`from app.services import *` dans app/__init__.py).
    """

    def __init__(self, app: Flask, config=None):
        self.__config = ContainerConfig()

        # 1. tout ce qui a été déclaré avec @injectable
        for dependency in registered_dependencies():
            self.__config.bind(dependency)

        # 2. crochet facultatif, utile dans les tests pour remplacer une
        #    dépendance par un double:
        #       Injector(app, config=lambda c: c.bind(
        #           DependencyConfig(UserService, FakeUserService, Scope.SINGLETON)))
        if config is not None:
            config(self.__config)

        # On accroche l'injecteur à l'app: c'est le seul objet global que Flask
        # nous donne, et @inject y accède via `from app import app`.
        app.injector = self

        self.__singleton = {}

    def __getitem__(self, item):
        """Permet la syntaxe injector['UserService']."""
        dep = self.__config.get(item)

        if dep is None:
            return None

        if dep.scope is Scope.SINGLETON:
            return self.__get_singleton(dep)

        if dep.scope is Scope.SCOPED:
            return self.__get_scoped(dep)

        return self.__get_transient(dep)

    def __get_singleton(self, dependency: DependencyConfig):
        # Créée une seule fois, puis mémorisée pour toute la vie du process.
        if self.__singleton.get(dependency.base.__name__) is None:
            self.__singleton[dependency.base.__name__] = dependency.implement()

        return self.__singleton[dependency.base.__name__]

    def __get_scoped(self, dependency: DependencyConfig):
        # `g` est l'espace de stockage que Flask remet à zéro à chaque requête:
        # c'est exactement la définition d'une dépendance "scoped".
        if not has_app_context():
            # Hors requête (script, shell, seed...) on ne peut pas être scoped,
            # on retombe donc sur une instance jetable.
            return self.__get_transient(dependency)

        scoped = g.setdefault('_injector_scoped', {})

        if scoped.get(dependency.base.__name__) is None:
            scoped[dependency.base.__name__] = dependency.implement()

        return scoped[dependency.base.__name__]

    def __get_transient(self, dependency: DependencyConfig):
        return dependency.implement()
