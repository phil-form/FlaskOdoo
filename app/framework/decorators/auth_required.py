import inspect
from functools import wraps

from flask import flash, redirect, request, url_for

from app.framework.decorators.inject import inject
from app.services.auth_service import AuthService


def auth_required(level=None, or_is_current_user=False):
    """Protège une vue MVC: il faut être connecté, et avoir le droit d'entrer.

        @app.get('/basket')
        @auth_required()                                   # connecté, c'est tout
        def basket_details(...): ...

        @app.get('/users')
        @auth_required(level="ADMIN")                       # rôle exigé
        def user_list(...): ...

        @app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
        @auth_required(or_is_current_user=True)             # propriétaire, ou ADMIN
        def user_update(user_id, ...): ...

    Les trois règles, dans cet ordre:

    1. un **ADMIN** passe partout — sinon il faudrait penser à lui donner aussi
       chacun des autres rôles;
    2. le **rôle demandé** (`level`) suffit, s'il y en a un;
    3. le **propriétaire** de la ressource passe, si `or_is_current_user=True`.

    `level=None` (le défaut) veut dire « aucun rôle particulier »: être
    authentifié suffit. C'est volontaire, et c'est ce qui rend la combinaison
    `or_is_current_user=True` sans `level` non seulement possible mais **juste**:
    elle signifie « le propriétaire, ou un admin ».

    Deux garde-fous sont posés à la DÉCLARATION de la vue (au démarrage de
    l'application, pas au moment d'une requête):

    - `or_is_current_user=True` sur une vue sans paramètre `user_id` ne pourrait
      jamais reconnaître le propriétaire, et se dégraderait silencieusement en
      « admin seulement »;
    - `level="USER"` avec `or_is_current_user=True` accorderait la ressource à
      **tout utilisateur connecté** (ils ont tous le rôle USER), la règle de
      propriété ne servant alors plus à rien. C'était un vrai piège de la
      première version de ce décorateur: silencieux, et seul un test le révélait.
      Il est maintenant refusé au démarrage.

    Version site web (MVC): pas de token, on s'appuie sur AuthService (session ou
    JWT selon l'implémentation enregistrée) et on REDIRIGE vers le login au lieu
    de renvoyer un 401.

    C'est un décorateur à paramètres, donc trois niveaux de fonctions:
      auth_required(...)            -> retourne le décorateur
        auth_required_decorator(f)  -> retourne le remplaçant de f
          function_wrapper(...)     -> le code exécuté à chaque requête
    """

    def auth_required_decorator(func):
        # --- garde-fous, une seule fois, au chargement du module -------------
        if or_is_current_user:
            # inspect.signature suit __wrapped__ (posé par @wraps dans @inject),
            # on voit donc la signature de la vue elle-même.
            if 'user_id' not in inspect.signature(func).parameters:
                raise ValueError(
                    f"auth_required(or_is_current_user=True) sur "
                    f"{func.__name__}(): la vue doit avoir un paramètre "
                    f"`user_id` (venant de l'URL), sinon la règle de propriété "
                    f"ne peut jamais s'appliquer.")

            if level == "USER":
                raise ValueError(
                    f"auth_required(level=\"USER\", or_is_current_user=True) sur "
                    f"{func.__name__}(): tout utilisateur connecté a le rôle "
                    f"USER, la ressource serait donc ouverte à tous et la règle "
                    f"de propriété inutile. Utilisez or_is_current_user=True "
                    f"seul (propriétaire ou ADMIN), ou un rôle privilégié.")

        @wraps(func)
        @inject
        def function_wrapper(*args, auth_service: AuthService, **kwargs):
            current_user = auth_service.get_current_user()

            # Pas connecté -> login, en mémorisant la page demandée pour y
            # revenir après connexion (paramètre ?next=).
            if current_user is None:
                flash("Veuillez vous connecter pour accéder à cette page.", "warning")
                return redirect(url_for('login', next=request.path))

            roles = current_user.role_names()

            # 1. un ADMIN passe partout
            if "ADMIN" in roles:
                return func(*args, **kwargs)

            # 2. le rôle demandé
            if level is not None and level in roles:
                return func(*args, **kwargs)

            # 3. le propriétaire de la ressource
            if or_is_current_user and current_user.user_id == kwargs.get('user_id'):
                return func(*args, **kwargs)

            # Aucun rôle exigé et aucune règle de propriété: être connecté suffit.
            if level is None and not or_is_current_user:
                return func(*args, **kwargs)

            flash("Vous n'avez pas les droits nécessaires.", "danger")
            return redirect(url_for('index'))

        return function_wrapper

    return auth_required_decorator
