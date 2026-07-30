from app.framework.injector import DependencyConfig, Scope, register_dependency


def injectable(cls=None, *, base=None, scope: Scope = Scope.SINGLETON):
    """Déclare une classe comme injectable. Remplace l'ancien injector_config.py.

    Trois usages:

        @injectable                                  # SINGLETON, demandé par son propre nom
        class ItemService(BaseService): ...

        @injectable(scope=Scope.TRANSIENT)           # autre durée de vie
        class MonService: ...

        @injectable(base=AuthService, scope=Scope.SCOPED)   # implémentation d'une interface
        class AuthServiceImpl(AuthService): ...

    - `base` = le type que les vues DEMANDENT (`auth_service: AuthService`).
      Par défaut, la classe elle-même. C'est ce qui permet de garder les
      controllers ignorants de l'implémentation concrète: ils annotent
      AuthService, l'injecteur livre AuthServiceImpl.
    - `scope` = la durée de vie, SINGLETON par défaut (voir Scope). C'est le bon
      choix pour un service sans état; un service qui mémorise quelque chose lié
      à l'utilisateur courant doit demander SCOPED.

    Comment ça marche: le décorateur est exécuté à l'import du module, il inscrit
    la classe dans le registre global de app/framework/injector.py, et retourne
    la classe INCHANGÉE (aucun wrapper, aucun comportement modifié). L'injecteur
    lit ensuite ce registre à sa création.

    Corollaire: un service jamais importé n'est jamais enregistré. C'est pour ça
    que app/__init__.py fait `from app.services import *` avant de créer
    l'injecteur.

    Note sur l'écriture du décorateur: il doit fonctionner avec ET sans
    parenthèses. Sans parenthèses, Python appelle injectable(MaClasse) -> `cls`
    est la classe. Avec parenthèses, il appelle d'abord injectable(scope=...)
    -> `cls` est None, et on doit retourner le vrai décorateur.

    `base` et `scope` sont keyword-only (le `*` dans la signature): écrire
    @injectable(AuthService) serait indistinguable de @injectable posé sur la
    classe AuthService.
    """

    def decorate(target):
        register_dependency(DependencyConfig(base or target, target, scope))

        return target

    # Utilisé avec parenthèses: @injectable(...) -> on rend le décorateur.
    if cls is None:
        return decorate

    # Utilisé nu: @injectable -> on décore tout de suite.
    return decorate(cls)
