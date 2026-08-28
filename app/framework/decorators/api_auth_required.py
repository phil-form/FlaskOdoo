from functools import wraps

from flask import request

from app.framework.api import json_error
from app.services.auth_service import AuthService
from app.framework.decorators.inject import inject


def api_auth_required(level=None):
    """Protège une route d'API. Le jumeau de @auth_required, en JSON.

        @api.get('/items')
        @api_auth_required()
        def api_item_list(...): ...

        @api.post('/items')
        @api_auth_required(level="ADMIN")
        def api_item_add(...): ...

    Trois différences avec la version MVC, et chacune a une raison.

    --- 1. On répond, on ne redirige pas -----------------------------------

    `@auth_required` redirige vers `/login` avec un message flash. Pour un
    client d'API, une redirection 302 vers une page HTML est une réponse
    incompréhensible: son parseur JSON échoue sur `<!DOCTYPE html>` et il
    signale « erreur de format » au lieu de « authentifiez-vous ».

    On rend donc les deux codes prévus pour ça, et la distinction compte:

    - **401 Unauthorized**: « je ne sais pas qui vous êtes » — le client peut
      réessayer avec un token (ou en rafraîchir un);
    - **403 Forbidden**: « je sais qui vous êtes, et non » — réessayer avec le
      même compte est inutile.

    Un 403 là où il fallait un 401 envoie le client dans une boucle de
    reconnexion; un 401 là où il fallait un 403 lui fait croire que son token
    est cassé.

    --- 2. Le token doit être dans l'en-tête -------------------------------

    `AuthServiceJwt` accepte le token dans un cookie **ou** dans
    `Authorization: Bearer`. Pour l'API, on exige l'en-tête.

    Ce n'est pas du purisme, c'est ce qui rend l'exemption CSRF sûre. Un cookie
    part TOUT SEUL, sur n'importe quelle requête, y compris celle déclenchée par
    un formulaire hébergé sur un autre site: c'est exactement le CSRF. Un
    en-tête `Authorization`, lui, doit être ajouté explicitement par le client —
    aucun site tiers ne peut le faire à sa place.

    D'où la règle, qui vaut bien au-delà de ce projet:

        API sans CSRF  =>  API qui n'accepte PAS les cookies d'authentification

    Exempter le blueprint de CSRF tout en acceptant le cookie ouvrirait toutes
    les routes d'écriture de l'application à n'importe quel site.

    --- 3. Pas de règle « propriétaire » ------------------------------------

    `or_is_current_user` n'existe pas ici: les routes d'API qui manipulent les
    données de l'utilisateur courant (le panier) les retrouvent par son
    identifiant de token, sans jamais lire un `user_id` d'URL. Il n'y a donc
    rien à comparer.
    """

    def api_auth_required_decorator(func):

        @wraps(func)
        @inject
        def function_wrapper(*args, auth_service: AuthService, **kwargs):
            entete = request.headers.get('Authorization', '')

            if not entete.startswith('Bearer '):
                # WWW-Authenticate est la réponse normalisée à un 401 (RFC 9110):
                # elle dit au client COMMENT s'authentifier. Beaucoup d'API
                # l'omettent; les clients génériques (et les navigateurs) la
                # lisent.
                reponse, statut = json_error("authentification requise", 401)

                return reponse, statut, {'WWW-Authenticate': 'Bearer'}

            current_user = auth_service.get_current_user()

            if current_user is None:
                return json_error("token absent, invalide ou expiré", 401)

            roles = current_user.role_names()

            # Mêmes règles que la version MVC: un ADMIN passe partout, sinon le
            # rôle demandé, sinon être authentifié suffit si aucun n'est exigé.
            if "ADMIN" in roles or level is None or level in roles:
                return func(*args, **kwargs)

            return json_error("droits insuffisants", 403, required_role=level)

        return function_wrapper

    return api_auth_required_decorator
