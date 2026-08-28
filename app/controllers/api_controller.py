"""L'API JSON — les mêmes services, une autre présentation.

C'est le point de l'étape, et il vaut la peine d'être dit avant de lire le
code: **aucun service n'a été modifié, aucun modèle, aucun mapper.** Toute la
logique métier était déjà écrite, testée et utilisée par les pages HTML. Ce
fichier ne fait que la rendre accessible sous une autre forme.

C'est le bénéfice, très concret, de trois décisions prises bien plus tôt:

- les **services** ne connaissent ni `request` ni `render_template` (étape 04):
  ils sont donc appelables depuis un controller HTML, un controller d'API, un
  seed ou une commande CLI;
- les **DTO** savent se rendre en types de base (`get_json_parsable()`, étape
  04). Cette méthode n'avait jamais servi — c'était pour aujourd'hui;
- l'**authentification par token** (étapes 14 et 15) fonctionne déjà sans
  cookie, donc sans navigateur.

Une API n'est pas une réécriture: c'est une deuxième façade sur le même métier.
Si l'ajouter demandait de toucher aux services, c'est que la logique avait fui
dans les controllers.

--- Blueprint plutôt que @app.route -----------------------------------------

Un Blueprint est un groupe de routes qu'on enregistre d'un coup, avec un
préfixe commun. Il donne ici trois choses qu'@app.route ne donne pas:

1. `url_prefix='/api'` écrit une seule fois;
2. un point d'accroche pour l'exemption CSRF (`csrf.exempt(api)`), qui ne doit
   surtout pas s'appliquer aux pages HTML;
3. une frontière lisible: tout ce qui est ici répond en JSON, rien d'autre.

--- Versionner l'URL --------------------------------------------------------

`/api/v1/...` serait plus prudent qu'`/api/...`: une API publique a des
clients qu'on ne contrôle pas et qu'on ne peut pas déployer. Le préfixe est le
seul moyen simple de faire coexister deux contrats. On s'en passe ici pour ne
pas alourdir les exemples — c'est un exercice, et ce serait une faute dans un
vrai produit.
"""
from flask import Blueprint, request

from app import app, csrf
from app.forms.basket.basket_add_item_form import BasketAddItemForm
from app.forms.item.item_form import ItemForm
from app.forms.user.user_login_form import UserLoginForm
from app.framework.api import (form_errors, json_body, json_error, json_ok,
                               paginate, pagination_args, to_formdata, to_json)
from app.framework.decorators.api_auth_required import api_auth_required
from app.framework.decorators.inject import inject
from app.services.auth_service import AuthService
from app.framework.rate_limiter import rate_limit
from app.framework.token_issuer import TokenIssuer
from app.services.basket_service import BasketService
from app.services.item_service import ItemService
from app.services.login_attempt_service import LoginAttemptService
from app.services.refresh_token_service import RefreshTokenService
from app.services.user_service import UserService

api = Blueprint('api', __name__, url_prefix='/api')

# EXEMPTION CSRF — et la seule chose qui la rend acceptable.
#
# Le jeton CSRF protège les requêtes authentifiées PAR COOKIE: le navigateur
# envoie le cookie tout seul, y compris pour une requête déclenchée par un site
# tiers, et seul un jeton qu'il ne peut pas lire prouve l'intention.
#
# Un client d'API n'a pas de cookie: il présente `Authorization: Bearer`, un
# en-tête qu'AUCUN site tiers ne peut ajouter à sa place. Le jeton CSRF n'a donc
# plus rien à protéger — il empêcherait juste tout client non-navigateur de
# fonctionner.
#
# La condition est stricte, et elle est appliquée par @api_auth_required:
# **ces routes n'acceptent pas le cookie d'authentification.** Exempter le
# blueprint tout en acceptant le cookie ouvrirait chaque route d'écriture à
# n'importe quel site du web.
csrf.exempt(api)


def form_json(classe_de_formulaire, **kwargs):
    """Un formulaire WTForms alimenté par un corps JSON.

    Les validators écrits à l'étape 04 (longueurs, plages, champs obligatoires)
    valent exactement autant pour un client d'API que pour un navigateur. Les
    réécrire à la main ici serait deux fois le travail et deux fois les bugs —
    et le jour où une règle change, une seule des deux façades la suivrait.

    Deux ajustements, et le premier est un vrai piège:

    - **`formdata=` et non `data=`.** Les deux « remplissent » le formulaire,
      mais pas de la même façon: `data` pose une valeur par défaut, `formdata`
      simule une saisie. Or `InputRequired` (celui du champ `stock`) regarde
      `field.raw_data`, qui n'est rempli QUE par `formdata`. Avec `data=`, il
      conclut « champ absent » et refuse **toutes** les créations d'article —
      y compris celles où `stock` vaut bien 0.

      C'est le même piège qu'à l'étape 04, où `DataRequired` refusait un stock
      à zéro parce que 0 est falsy. Et il ne suffit pas de changer de
      paramètre: `to_formdata` explique pourquoi les valeurs doivent en plus
      être converties en chaînes, sinon l'entier `0` disparaît quand même.

    - `meta={'csrf': False}`: le jeton n'a pas de sens ici (voir `csrf.exempt`
      plus haut), et sans ça `validate()` échouerait toujours.
    """
    return classe_de_formulaire(formdata=to_formdata(json_body()),
                                meta={'csrf': False}, **kwargs)


# --- authentification -------------------------------------------------------

@api.post('/auth/login')
@rate_limit(10, 60, bucket='api_login')
@inject
def api_login(user_service: UserService, token_issuer: TokenIssuer,
              refresh_token_service: RefreshTokenService,
              login_attempt_service: LoginAttemptService):
    """Échange identifiant + mot de passe contre une paire de tokens.

    Mêmes protections que la page HTML — verrou de compte et limite de débit.
    Il serait absurde de durcir `/login` pendant des étapes entières et
    d'ouvrir une porte non gardée à côté: un attaquant prend toujours la porte
    la moins protégée.
    """
    form = form_json(UserLoginForm)

    if not form.validate():
        return json_error("données invalides", 422, fields=form_errors(form))

    bloque = login_attempt_service.locked_seconds(form.username.data)

    if bloque > 0:
        return json_error("compte temporairement verrouillé", 429,
                          retry_after=bloque)

    user = user_service.login(form)

    if user is None:
        login_attempt_service.record_failure(form.username.data)

        # Message aussi vague qu'en HTML: on ne dit pas si c'est le nom ou le
        # mot de passe. Une API qui répond « utilisateur inconnu » est un
        # énumérateur de comptes offert à qui veut.
        return json_error("identifiants invalides", 401)

    login_attempt_service.record_success(form.username.data)

    return json_ok(_emettre_tokens(user, token_issuer, refresh_token_service))


@api.post('/auth/refresh')
@inject
def api_refresh(user_service: UserService, token_issuer: TokenIssuer,
                refresh_token_service: RefreshTokenService):
    """Renouvelle l'access token à partir du refresh token.

    Exactement la même rotation qu'à l'étape 15 (et la même détection de
    rejeu): le service est partagé, seul le transport change — le refresh token
    arrive dans le corps JSON au lieu d'un cookie `SameSite=Strict`.

    Un client d'API doit donc le stocker lui-même, et c'est le point faible du
    schéma: dans un navigateur, `localStorage` est lisible par n'importe quel
    XSS. Pour une application mono-page, le cookie httpOnly reste le moins
    mauvais choix — d'où la coexistence des deux transports.
    """
    ancien = json_body().get('refresh_token')

    if not ancien:
        return json_error("refresh_token manquant", 400)

    resultat = refresh_token_service.rotate(ancien)

    if resultat is None:
        return json_error("refresh token inconnu, expiré ou rejoué", 401)

    user_id, nouveau_refresh, _famille = resultat
    user = user_service.find_one(user_id)

    if user is None:
        return json_error("compte introuvable", 401)

    return json_ok({
        'access_token': token_issuer.encode(user),
        'refresh_token': nouveau_refresh,
        'token_type': 'Bearer',
    })


@api.post('/auth/logout')
@api_auth_required()
@inject
def api_logout(refresh_token_service: RefreshTokenService):
    """Révoque le refresh token fourni.

    Il n'y a rien à « déconnecter » côté serveur pour l'access token: il est
    sans état, il vivra jusqu'à son expiration. C'est la limite du JWT,
    mesurée à l'étape 15 — et la raison pour laquelle il est court.
    """
    refresh = json_body().get('refresh_token')

    if refresh:
        refresh_token_service.revoke(refresh)

    return json_ok(status=200, revoked=bool(refresh))


def _emettre_tokens(user, token_issuer: TokenIssuer,
                    refresh_token_service: RefreshTokenService) -> dict:
    return {
        'access_token': token_issuer.encode(user),
        'refresh_token': refresh_token_service.issue(user.user_id),
        'token_type': 'Bearer',
        'user': to_json(user),
    }


# --- utilisateur courant ----------------------------------------------------

@api.get('/me')
@api_auth_required()
@inject
def api_me(auth_service: AuthService):
    """Le profil du porteur du token.

    Route très utile en pratique: elle permet à un client de vérifier qu'un
    token stocké est encore valable, et de récupérer les rôles pour afficher ou
    non un bouton — sans jamais s'y fier pour la sécurité, qui reste côté
    serveur.
    """
    return json_ok(auth_service.get_current_user())


# --- catalogue --------------------------------------------------------------

@api.get('/items')
@inject
def api_item_list(item_service: ItemService):
    """Le catalogue, paginé. Route PUBLIQUE, comme la page HTML."""
    page, per_page = pagination_args()
    elements, meta = paginate(item_service.find_all(), page, per_page)

    return json_ok(elements, pagination=meta)


@api.get('/items/<int:item_id>')
@inject
def api_item_details(item_id: int, item_service: ItemService):
    item = item_service.find_one(item_id)

    if item is None:
        return json_error("article introuvable", 404)

    return json_ok(item)


@api.post('/items')
@api_auth_required(level="ADMIN")
@inject
def api_item_add(item_service: ItemService):
    form = form_json(ItemForm)

    if not form.validate():
        return json_error("données invalides", 422, fields=form_errors(form))

    item = item_service.insert(form)

    if item is None:
        return json_error("création impossible", 400)

    # 201 Created, et l'en-tête Location vers la ressource créée. Les deux font
    # partie du contrat HTTP: un client générique sait alors où aller la
    # relire, sans deviner l'URL.
    reponse, statut = json_ok(item, status=201)

    return reponse, statut, {'Location': f"/api/items/{item.item_id}"}


@api.put('/items/<int:item_id>')
@api_auth_required(level="ADMIN")
@inject
def api_item_update(item_id: int, item_service: ItemService):
    form = form_json(ItemForm)

    if not form.validate():
        return json_error("données invalides", 422, fields=form_errors(form))

    item = item_service.update(item_id, form)

    if item is None:
        return json_error("article introuvable", 404)

    return json_ok(item)


@api.delete('/items/<int:item_id>')
@api_auth_required(level="ADMIN")
@inject
def api_item_delete(item_id: int, item_service: ItemService):
    if item_service.delete(item_id) is None:
        return json_error("article introuvable", 404)

    # 204 No Content: la suppression a réussi, il n'y a rien à dire de plus.
    # Renvoyer {"success": true} serait du bruit — le code de statut le dit
    # déjà, et mieux.
    return '', 204


# --- panier -----------------------------------------------------------------

@api.get('/basket')
@api_auth_required()
@inject
def api_basket(auth_service: AuthService, basket_service: BasketService):
    """Le panier de l'utilisateur courant.

    Remarquez l'absence de `user_id` dans l'URL: le panier est TOUJOURS
    retrouvé à partir du token. C'est la même règle qu'en HTML, et c'est ce qui
    rend impossible de lire le panier de quelqu'un d'autre en changeant un
    chiffre — la classe de faille la plus courante des API (IDOR).
    """
    return json_ok(basket_service.find_current(
        auth_service.get_current_user().user_id))


@api.post('/basket/items')
@api_auth_required()
@inject
def api_basket_add(auth_service: AuthService, basket_service: BasketService):
    form = form_json(BasketAddItemForm)

    if not form.validate():
        return json_error("données invalides", 422, fields=form_errors(form))

    basket = basket_service.add_item(
        auth_service.get_current_user().user_id, form)

    if basket is None:
        return json_error("article introuvable ou stock insuffisant", 409)

    return json_ok(basket)


@api.delete('/basket/items/<int:item_id>')
@api_auth_required()
@inject
def api_basket_remove(item_id: int, auth_service: AuthService,
                      basket_service: BasketService):
    basket = basket_service.remove_item(
        auth_service.get_current_user().user_id, item_id)

    if basket is None:
        return json_error("article absent du panier", 404)

    return json_ok(basket)


@api.post('/basket/checkout')
@api_auth_required()
@inject
def api_basket_checkout(auth_service: AuthService,
                        basket_service: BasketService):
    current_user = auth_service.get_current_user()

    # Même règle métier que la page HTML: pas de commande sans adresse
    # confirmée. Elle est vérifiée dans le controller, ici comme là-bas — ce
    # qui veut dire qu'elle est écrite DEUX fois. Le README de l'étape en
    # discute: c'est la règle qui aurait dû vivre dans le service.
    if not current_user.email_verified:
        return json_error("adresse email non confirmée", 403)

    basket = basket_service.checkout(current_user.user_id)

    if basket is None:
        return json_error("panier vide ou stock insuffisant", 409)

    return json_ok(basket)


# --- administration ---------------------------------------------------------

@api.get('/users')
@api_auth_required(level="ADMIN")
@inject
def api_user_list(user_service: UserService):
    # Le DTO complet: l'API rend ici tout ce que `UserDTO` porte. Une étape
    # ultérieure y reviendra — une réponse JSON est lue par des machines, on
    # n'y met pas un champ « au cas où ».
    page, per_page = pagination_args()
    elements, meta = paginate(user_service.find_all(), page, per_page)

    return json_ok(elements, pagination=meta)


app.register_blueprint(api)


# --- erreurs en JSON --------------------------------------------------------

@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(500)
def erreurs_json(erreur):
    """Une API ne doit JAMAIS répondre du HTML.

    Sans ce gestionnaire, `/api/inexistant` renvoie la page d'erreur de Flask:
    le client reçoit `<!DOCTYPE html>`, son parseur JSON échoue, et son message
    d'erreur parle de syntaxe au lieu de parler de route introuvable.

    Pourquoi un gestionnaire global avec un test sur le chemin, plutôt qu'un
    `@api.errorhandler`? Parce qu'un 404 se produit avant que Flask ait pu
    associer la requête à un blueprint: il ne SAIT pas que l'URL visée était
    celle de l'API. Le préfixe d'URL est la seule information disponible à ce
    moment-là.

    Le repli `return erreur` laisse les pages HTML se comporter comme avant:
    ce gestionnaire ne s'occupe que de `/api`.
    """
    if not request.path.startswith('/api'):
        return erreur

    code = getattr(erreur, 'code', 500)
    messages = {404: "ressource introuvable",
                405: "méthode non autorisée",
                500: "erreur interne"}

    return json_error(messages.get(code, "erreur"), code)
