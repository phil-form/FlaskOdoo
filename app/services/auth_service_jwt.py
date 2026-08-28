import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, redirect, request, url_for

from app import app
from app.dtos.user_dto import UserDTO
from app.framework.decorators.inject import inject
from app.framework.decorators.injectable import injectable
from app.framework.injector import Scope
from app.framework.token_issuer import TokenIssuer
from app.services.auth_service import AuthService
from app.services.refresh_token_service import RefreshTokenService
from app.services.user_service import UserService

# Nom du cookie qui transporte l'access token. Le préfixe __Host- (production)
# fait refuser par le navigateur tout cookie qui ne serait pas Secure, ou posé
# sur un autre domaine/chemin: un sous-domaine compromis ne peut plus écrire le
# nôtre.
COOKIE_NAME = "access_token" if app.debug else "__Host-access_token"

# LE CHEMIN DU REFRESH TOKEN — et le seul.
#
# Le refresh token est le secret le plus précieux du dispositif: il vaut sept
# jours d'accès, alors que l'access token en vaut quinze minutes. Il n'a aucune
# raison d'accompagner la requête d'une image, d'une page de catalogue ou d'un
# formulaire. Confiné à ce chemin, le navigateur ne l'envoie qu'à la seule route
# qui sait quoi en faire — donc jamais dans les journaux d'accès des autres
# routes, jamais dans un `Referer`, jamais dans une requête que le reste du code
# pourrait trahir.
REFRESH_PATH = "/auth/refresh"

# ATTENTION AU PRÉFIXE: __Secure- et non __Host-.
#
# `__Host-` impose au cookie trois conditions, et la troisième est celle qui
# nous concerne: Secure, pas d'attribut Domain, et **Path=/ exactement**. Un
# cookie `__Host-refresh_token` posé sur `/auth/refresh` est donc SILENCIEUSEMENT
# REFUSÉ par le navigateur: pas d'erreur, pas de message, juste une déconnexion
# au bout de quinze minutes que rien n'explique.
#
# `__Secure-` n'exige que Secure, et se contente d'un Path restreint. On échange
# la garantie « aucun sous-domaine ne peut écrire ce cookie » contre le
# confinement de chemin — pour ce cookie-là, c'est le bon échange.
REFRESH_COOKIE_NAME = "refresh_token" if app.debug else "__Secure-refresh_token"

# Clés de `g` utilisées pour communiquer avec le after_request en bas de fichier.
G_SET = '_jwt_a_poser'
G_CLEAR = '_jwt_a_supprimer'
G_REFRESH_SET = '_refresh_a_poser'


# DEUX enregistrements sur la même classe (étape 16). C'est possible parce que
# @injectable retourne la classe INCHANGÉE: chaque décorateur ajoute une ligne
# au registre, l'un sous 'AuthService', l'autre sous 'TokenIssuer'.
#
# Un controller MVC demande AuthService (« qui est connecté? »), un controller
# d'API demande TokenIssuer (« fabrique-moi un token »), et tous deux reçoivent
# la même instance — scope SCOPED, donc une par requête.
@injectable(base=AuthService, scope=Scope.SCOPED)
@injectable(base=TokenIssuer, scope=Scope.SCOPED)
class AuthServiceJwt(AuthService, TokenIssuer):
    """Authentification par JWT, à la place de la session Flask.

    Ce qui change par rapport à AuthServiceImpl:

    - l'identité ne vit plus côté serveur, elle est **dans le token**, signé;
    - il n'y a plus d'état de session à faire tourner, ce qui rend la « rotation
      de session » de l'étape 12 sans objet: l'attaque de session fixation
      suppose un identifiant de session réutilisable, et il n'y en a plus;
    - le token **prouve** l'identité, il ne la **décrit** pas: on n'en retient
      que `sub`, et les droits sont relus en base à chaque requête. Un rôle
      retiré prend donc effet tout de suite.

    Ce que le JWT achète, et ce qu'il n'achète pas — parce que c'est là que la
    plupart des projets se trompent:

    - il achète l'absence d'**état de session côté serveur**: rien à stocker,
      rien à répliquer entre deux processus, et le même mécanisme marche pour un
      client d'API qui n'a pas de cookie;
    - il n'achète **pas** l'absence de requête SQL. On lit la base à chaque
      requête authentifiée, exactement comme la version session. Mettre les
      rôles dans les claims économise cette requête et les FIGE jusqu'à
      l'expiration du token: c'est un cache d'autorisation qu'on ne peut pas
      invalider, et on ne l'échange pas contre une requête indexée.

    Ce qui ne change pas: **rien dans les controllers**. Ils annotent
    `auth_service: AuthService`, et c'est `@injectable(base=...)` qui décide de
    l'implémentation livrée. C'est le bénéfice concret de l'interface de
    l'étape 06, et la raison pour laquelle elle existait avant d'être utile.

    --- DEUX TOKENS, DEUX TRANSPORTS ---------------------------------------

    Les deux tokens ne voyagent pas de la même façon, et ce n'est pas un détail
    d'implémentation: c'est le cœur de l'étape.

    **L'access token: en-tête OU cookie.** `read_token()` lit d'abord
    `Authorization: Bearer`, puis le cookie. Les deux transports coexistent
    parce qu'ils servent deux clients différents:

    - un **client d'API** (mobile, script, service) présente l'en-tête. Il n'a
      pas de navigateur, donc pas de cookie, et il stocke le token lui-même —
      dans un navigateur, ce serait `localStorage`, lisible par n'importe quel
      XSS;
    - un **navigateur** sur nos pages HTML reçoit un cookie `httpOnly`, que le
      JavaScript ne peut pas lire. Mais un cookie part TOUT SEUL, y compris sur
      une requête déclenchée par un site tiers: la protection **CSRF reste donc
      indispensable**. C'est l'erreur classique — « je suis passé au JWT, je
      n'ai plus besoin de CSRF » — et elle est fausse dès que le token est dans
      un cookie.

    L'en-tête est lu en premier: un client qui prend la peine de le poser sait
    ce qu'il fait, et ne doit pas se retrouver authentifié comme quelqu'un
    d'autre à cause d'un cookie traînant dans son navigateur.

    **Le refresh token: cookie uniquement, et sur un seul chemin.** Voir
    `REFRESH_PATH` plus haut. La conséquence est visible et assumée: le
    renouvellement n'est plus silencieux, c'est un aller-retour (voir
    `renouveler_avant_la_vue` en bas de fichier).
    """

    ALGORITHM = "HS256"

    @inject
    def __init__(self, user_service: UserService,
                 refresh_token_service: RefreshTokenService):
        self.__user_service = user_service
        self.__refresh_token_service = refresh_token_service
        # 15 minutes au lieu de 60: on peut se permettre un access token court
        # maintenant qu'un refresh token le renouvelle sans redemander le mot de
        # passe. C'est tout l'intérêt de la paire.
        self.__minutes = int(os.environ.get("JWT_ACCESS_MINUTES", 15))
        self.__current_user: UserDTO | None = None
        self.__loaded = False

    # --- lecture ------------------------------------------------------------

    def get_current_user(self) -> UserDTO | None:
        if self.__loaded:
            return self.__current_user

        self.__loaded = True
        token = self.read_token()
        claims = self.decode(token) if token else None

        if claims is None:
            # Pas de renouvellement silencieux ICI, contrairement à la première
            # version de l'étape 15: le cookie de refresh n'arrive tout
            # simplement pas jusqu'à cette requête, il est confiné à
            # REFRESH_PATH. Le renouvellement est devenu un aller-retour
            # explicite, déclenché par `renouveler_avant_la_vue` (bas de
            # fichier) AVANT que la vue ne s'exécute.
            return None

        # --- LE TOKEN AUTHENTIFIE, LA BASE AUTORISE -------------------------
        # On ne retient du token qu'une seule chose: `sub`, l'identifiant. Les
        # rôles, l'email vérifié, l'existence même du compte sont relus en base.
        #
        # Pourquoi se méfier d'un token qu'on a signé soi-même? Parce que la
        # signature prouve qu'il n'a pas été MODIFIÉ, pas qu'il est encore VRAI.
        # Un claim est une photo prise à l'émission:
        #
        # - on retire le rôle ADMIN à un compte: son token le dit toujours
        #   admin, et il le reste jusqu'à l'expiration. Une révocation qui met
        #   quinze minutes à s'appliquer n'est pas une révocation;
        # - un compte confirme son adresse: son token dit encore le contraire,
        #   le bandeau reste affiché et la commande reste refusée. Le lien de
        #   confirmation est souvent ouvert dans un AUTRE navigateur, on ne peut
        #   donc même pas compter sur cette requête-là pour réémettre le cookie.
        #
        # Le prix: une requête SQL par requête HTTP authentifiée. C'est la plus
        # chaude du projet, d'où le chargement anticipé des rôles dans
        # `UserService.find_one_entity` (étape 20) — une requête indexée, deux
        # jointures, et le droit de dire « non » tout de suite.
        self.__current_user = self.user_from_claims(claims)

        if self.__current_user is None:
            # Token valide, compte disparu ou désactivé. Le cookie ne sert plus
            # à rien: on l'efface, sinon le navigateur continue de le présenter
            # (et de payer une requête SQL) jusqu'à son expiration.
            setattr(g, G_CLEAR, True)

        return self.__current_user

    def is_authenticated(self) -> bool:
        return self.get_current_user() is not None

    # --- écriture -----------------------------------------------------------

    def renouveler(self) -> UserDTO | None:
        """Échange le refresh token contre un nouvel access token (rotation).

        **Publique**, et appelée depuis une seule route: `jwt_refresh`, en bas
        de fichier. C'est la seule requête à laquelle le navigateur joint le
        cookie de refresh, donc la seule où cette méthode peut aboutir.

        Trois règles importantes:

        1. **rotation**: le refresh token est consommé et remplacé. Un token qui
           resterait valable des jours entiers après usage serait aussi dangereux
           qu'un mot de passe volé.
        2. **rechargement depuis la base**: on relit le compte pour vérifier
           qu'il existe encore avant d'émettre un nouvel access token. Depuis
           que `get_current_user` relit la base à chaque requête, ce n'est plus
           ici que se joue la fraîcheur des droits — mais ça reste le bon
           endroit pour refuser de renouveler le token d'un compte disparu.
        3. **on efface les cookies dès que ça échoue**. Sans ça, un access token
           périmé resterait dans le navigateur, `renouveler_avant_la_vue`
           redirigerait à nouveau vers cette route, qui échouerait à nouveau:
           une boucle de redirections dont l'utilisateur ne sort pas.
        """
        refresh = request.cookies.get(REFRESH_COOKIE_NAME)

        if not refresh:
            # Un access token sans refresh token est une session morte: le
            # navigateur a perdu (ou n'a jamais reçu) la moitié qui compte.
            setattr(g, G_CLEAR, True)
            return None

        resultat = self.__refresh_token_service.rotate(refresh)

        if resultat is None:
            # Inconnu, expiré, ou rejeu (la famille vient d'être révoquée):
            # on efface les cookies pour forcer une vraie reconnexion.
            setattr(g, G_CLEAR, True)
            return None

        user_id, nouveau_refresh, famille = resultat
        user = self.__user_service.find_one(user_id)

        if user is None:
            # Compte supprimé ou désactivé entre-temps: on ne renouvelle pas.
            setattr(g, G_CLEAR, True)
            return None

        app.logger.debug(f"jwt: access token renouvelé pour {user.username}")

        setattr(g, G_SET, self.encode(user, famille))
        setattr(g, G_REFRESH_SET, nouveau_refresh)
        self.__current_user = user
        self.__loaded = True

        return user

    def login(self, user: UserDTO):
        # Une connexion = une nouvelle FAMILLE de refresh tokens. Les familles
        # précédentes restent valables: se connecter sur son téléphone ne doit pas
        # déconnecter l'ordinateur.
        #
        # L'identifiant de famille est tiré ICI et non par le service, parce que
        # l'access token doit le porter (claim `fam`): c'est ce qui permettra à
        # `logout()` de révoquer la bonne famille sans jamais voir le refresh
        # token lui-même.
        famille = secrets.token_hex(16)

        # On ne stocke rien: on demande au after_request de poser les cookies. Le
        # service ne manipule pas la réponse lui-même — au moment où le
        # controller appelle login(), la réponse n'existe pas encore.
        setattr(g, G_SET, self.encode(user, famille))
        setattr(g, G_REFRESH_SET,
                self.__refresh_token_service.issue(user.user_id,
                                                   family_id=famille))
        self.__current_user = user
        self.__loaded = True

    def logout(self):
        """Déconnexion: effacer les cookies NE SUFFIT PAS.

        Un refresh token effacé du navigateur reste valable sept jours en base.
        Si une copie a fuité, se déconnecter ne protège de rien — il faut le
        révoquer côté serveur.

        Sauf qu'ici, on ne l'a pas: `/logout` n'est pas sous REFRESH_PATH, le
        navigateur ne joint donc pas le cookie. C'est le prix du confinement, et
        c'est exactement à ça que sert le claim `fam`: l'access token, lui, est
        bien présent, et il porte l'identifiant de sa famille de refresh tokens.
        On révoque la famille entière — c'est-à-dire cet appareil, et lui seul.
        """
        token = self.read_token()
        claims = self.decode(token) if token else None
        famille = (claims or {}).get('fam')

        if famille:
            self.__refresh_token_service.revoke_family(famille)
        else:
            # Access token périmé ou absent: on ne sait pas quoi révoquer. Ça ne
            # devrait pas arriver (le renouvellement passe avant la vue), mais
            # se taire serait pire que de le dire.
            app.logger.info("jwt: déconnexion sans claim `fam`, rien à révoquer")

        setattr(g, G_CLEAR, True)
        self.__current_user = None
        self.__loaded = True

    # --- token --------------------------------------------------------------

    def encode(self, user: UserDTO, famille: str | None = None) -> str:
        now = datetime.now(timezone.utc)

        claims = {
            # Claims standards (RFC 7519): sub = sujet, iat = émis à,
            # exp = expire à. PyJWT vérifie `exp` tout seul au décodage.
            'sub': str(user.user_id),
            'iat': now,
            'exp': now + timedelta(minutes=self.__minutes),
            # Le SEUL claim applicatif, et il n'autorise RIEN: il sert aux
            # logs et au débogage (« ce token est celui de qui? »).
            #
            # Ce qui a été retiré d'ici est le sujet: `roles`, `email_verified`
            # et `email`. Un claim qui existe finit toujours par servir à
            # décider — et il décide alors avec la valeur qu'il avait à
            # l'émission. Le plus sûr est qu'il n'existe pas.
            'username': user.username,
        }

        if famille is not None:
            # `fam`: l'identifiant de la FAMILLE de refresh tokens à laquelle ce
            # token appartient. C'est OIDC qui appelle ça `sid`.
            #
            # Est-ce que ça contredit « le token authentifie, la base
            # autorise »? Non, et la distinction vaut d'être posée: `fam`
            # n'accorde aucun droit, ne se compare à aucun rôle, et n'ouvre
            # aucune porte. Il désigne une ligne à révoquer, et une révocation
            # ratée ne donne accès à rien. Un claim devient dangereux quand il
            # sert à dire OUI; celui-ci ne sert qu'à dire « oublie cet
            # appareil ».
            #
            # Il est optionnel parce qu'un client d'API n'en a pas besoin: il
            # détient son refresh token et le présente lui-même pour le révoquer.
            claims['fam'] = famille

        # JWT_SECRET, et pas SECRET_KEY: séparation des clés. La même valeur
        # signerait à la fois les cookies de session et les jetons CSRF de
        # Flask, et les tokens que des clients d'API gardent des heures. Deux
        # usages, deux durées de vie, deux rotations: le jour où l'une fuite, on
        # ne veut pas avoir tout perdu — et faire tourner l'une ne doit pas
        # déconnecter tout le monde de l'autre.
        return jwt.encode(claims, app.config['JWT_SECRET'], algorithm=self.ALGORITHM)

    def decode(self, token: str) -> dict | None:
        try:
            return jwt.decode(token, app.config['JWT_SECRET'],
                              # algorithms= est OBLIGATOIRE, et c'est une liste
                              # blanche. Sans elle, un attaquant présente un
                              # token signé avec l'algorithme "none" et se fait
                              # passer pour qui il veut: c'est la faille la plus
                              # connue du JWT.
                              algorithms=[self.ALGORITHM])
        except jwt.ExpiredSignatureError:
            app.logger.info("jwt: token expiré")
            return None
        except jwt.InvalidTokenError as e:
            # Signature invalide, structure cassée, algorithme refusé...
            app.logger.warning(f"jwt: token invalide ({e})")
            return None

    # --- utilitaires --------------------------------------------------------

    @staticmethod
    def read_token() -> str | None:
        """L'access token, où qu'il soit: en-tête d'abord, cookie ensuite.

        L'ordre compte. Un client qui pose `Authorization: Bearer` a fait un
        choix explicite; si un cookie traînait dans le même navigateur, le lire
        en priorité authentifierait quelqu'un d'autre que celui que le client
        croit être.
        """
        entete = request.headers.get('Authorization', '')

        if entete.startswith('Bearer '):
            return entete[len('Bearer '):]

        return request.cookies.get(COOKIE_NAME)

    def user_from_claims(self, claims: dict) -> UserDTO | None:
        """L'utilisateur désigné par le token, relu en base.

        Le nom de la méthode compte: elle s'appelait `dto_from_claims` et
        fabriquait le DTO **à partir** des claims. Elle ne le fait plus, et le
        nom ne doit pas continuer à le prétendre.

        `int(claims['sub'])`: la RFC 7519 impose une CHAÎNE pour `sub`. Le cast
        est explicite parce qu'un `filter_by(user_id="3")` marche par chance
        (PostgreSQL convertit) jusqu'au jour où la comparaison se fait en
        Python et échoue sans bruit.

        Renvoie None si le compte n'existe plus: un token valide qui désigne un
        fantôme n'authentifie personne. C'est exactement ce que fait déjà la
        version session (`AuthServiceImpl`) — les deux implémentations lisent la
        base, la seule différence est **où est rangée l'identité**.
        """
        try:
            user_id = int(claims['sub'])
        except (KeyError, TypeError, ValueError):
            # Un token que NOUS avons signé n'a aucune raison d'arriver ici. Si
            # ça arrive, c'est que la clé a fui ou que le format a changé: dans
            # les deux cas on veut le savoir.
            app.logger.warning("jwt: claim `sub` absent ou illisible")
            return None

        return self.__user_service.find_one(user_id)


# --- le renouvellement, en aller-retour --------------------------------------
#
# Tout ce qui suit est enregistré à l'import du module — donc via le
# `from app.services import *` de app/__init__.py. L'implémentation JWT reste
# autonome: rien à ajouter dans app/__init__.py, ni dans un controller.


def _token_perime(jeton: str) -> bool:
    """Vrai si le token est bien le nôtre, mais périmé.

    Trois cas, et un seul justifie une redirection:

    - **cookie absent**: visiteur anonyme, il n'y a rien à renouveler;
    - **cookie illisible** (signature fausse, clé changée, format cassé): le
      renouvellement n'y changerait rien;
    - **cookie valide mais expiré**: là, et là seulement, un refresh token peut
      encore sauver la session.
    """
    try:
        jwt.decode(jeton, app.config['JWT_SECRET'],
                   algorithms=[AuthServiceJwt.ALGORITHM])
    except jwt.ExpiredSignatureError:
        return True
    except jwt.InvalidTokenError:
        return False

    return False


def _destination_locale(cible: str | None) -> str:
    """La page où revenir après le renouvellement — jamais un autre site.

    Sans ce filtre, `/auth/refresh?next=https://exemple-malveillant` fait de
    l'application un tremplin: le lien affiché est le nôtre, la page d'arrivée
    ne l'est pas. C'est la faille « open redirect », et le fait qu'elle se
    corrige en trois lignes est précisément la raison pour laquelle on l'oublie.

    `//autre-site` est refusé aussi: c'est une URL relative au protocole, un
    navigateur y voit bien un autre domaine.
    """
    if not cible or not cible.startswith('/') or cible.startswith('//'):
        return '/'

    return cible


@app.get(REFRESH_PATH)
@inject
def jwt_refresh(auth_service: AuthService):
    """La seule route à laquelle le navigateur joint le refresh token.

    Le scénario complet, vu du navigateur:

        GET /basket            -> l'access token a expiré
                                  302 vers /auth/refresh?next=/basket
        GET /auth/refresh      -> le cookie de refresh est joint (c'est son
                                  chemin), rotation, deux cookies neufs
                                  302 vers /basket
        GET /basket            -> l'access token est frais, la page s'affiche

    Deux requêtes de plus, une seule fois toutes les quinze minutes. C'est le
    coût du confinement, et il est faible; ce qu'on achète en échange, c'est que
    le secret à sept jours ne traîne pas dans chacune des autres requêtes.

    `auth_service` est forcément un `AuthServiceJwt`: cette route n'est déclarée
    que par CE module, qui n'est lu que si l'implémentation JWT est celle qu'on
    a enregistrée. La version session n'a ni cette route ni ce besoin.
    """
    suite = _destination_locale(request.args.get('next'))

    if auth_service.renouveler() is None:
        # Échec: `renouveler` a déjà demandé l'effacement des cookies, il n'y
        # aura donc pas de boucle. On envoie vers le login en gardant la
        # destination: l'utilisateur retrouvera sa page après s'être reconnecté.
        return redirect(url_for('login', next=suite))

    return redirect(suite)


@app.before_request
def renouveler_avant_la_vue():
    """Détourne la requête vers /auth/refresh quand l'access token a expiré.

    Pourquoi avant la vue, et pas dans `get_current_user`? Parce qu'un service
    ne peut pas rediriger: quand le controller l'appelle, il est trop tard pour
    changer de page. Le `before_request` est le seul endroit où l'on peut encore
    dire « pas cette vue, celle-là d'abord ».

    Les quatre garde-fous, tous nécessaires:

    - **GET seulement.** Rediriger un POST perdrait le corps de la requête —
      le formulaire serait rejoué vide. Un POST avec un token périmé est donc
      simplement non authentifié, et l'utilisateur revient au login. C'est la
      régression assumée de cette étape, et la raison pour laquelle l'access
      token ne dure pas trente secondes.
    - **pas d'en-tête `Authorization`.** Un client d'API n'attend pas une
      redirection vers du HTML; il renouvelle lui-même, en présentant son
      refresh token (voir l'API des étapes suivantes).
    - **pas sur REFRESH_PATH lui-même**, sinon la route ne s'exécute jamais.
    - **pas sur les fichiers statiques**: rediriger une feuille de style est
      inutile, et multiplie les allers-retours par le nombre d'images de la page.
    """
    if request.method != 'GET' or request.endpoint == 'static':
        return None

    if request.path.startswith(REFRESH_PATH):
        return None

    if request.headers.get('Authorization', '').startswith('Bearer '):
        return None

    jeton = request.cookies.get(COOKIE_NAME)

    if jeton is None or not _token_perime(jeton):
        return None

    # `full_path` garde la query string, mais ajoute un '?' même quand il n'y en
    # a pas: sans ce nettoyage, on reviendrait sur `/basket?` — ça marche, mais
    # ça s'affiche dans la barre d'adresse et personne ne comprend pourquoi.
    suite = request.full_path

    if suite.endswith('?'):
        suite = suite[:-1]

    return redirect(url_for('jwt_refresh', next=suite))


@app.after_request
def ecrire_cookie_jwt(response):
    """Pose ou supprime les cookies des tokens, selon ce que la vue a demandé."""
    token = getattr(g, G_SET, None)

    if token is not None:
        response.set_cookie(
            COOKIE_NAME, token,
            # httponly: invisible à document.cookie -> un XSS ne vole pas le token
            httponly=True,
            # secure: pas de token en clair sur le réseau (désactivé en debug,
            # sinon plus de connexion possible sur http://localhost)
            secure=not app.debug,
            samesite='Lax',
            # LE COOKIE VIT PLUS LONGTEMPS QUE LE TOKEN QU'IL PORTE, et c'est
            # volontaire. Un cookie qui expirerait en même temps que le token
            # disparaîtrait du navigateur, et un visiteur périmé deviendrait
            # indiscernable d'un visiteur anonyme: `renouveler_avant_la_vue`
            # n'aurait plus rien à détecter et le renouvellement ne se
            # déclencherait jamais.
            #
            # Ça ne coûte aucune sécurité: ce qui fait foi, c'est `exp`, qui est
            # signé. Un cookie gardé plus longtemps ne prolonge rien, il permet
            # juste de constater la péremption.
            max_age=int(os.environ.get("JWT_REFRESH_DAYS", 7)) * 86400,
            path='/')

    refresh = getattr(g, G_REFRESH_SET, None)

    if refresh is not None:
        response.set_cookie(
            REFRESH_COOKIE_NAME, refresh,
            httponly=True,
            secure=not app.debug,
            # 'Strict' et non 'Lax': ce cookie ne sert QUE sur notre site, jamais
            # sur une navigation venue d'ailleurs. Aucune raison d'être plus
            # permissif que nécessaire.
            samesite='Strict',
            max_age=int(os.environ.get("JWT_REFRESH_DAYS", 7)) * 86400,
            # Le confinement de chemin. Le navigateur n'enverra ce cookie qu'aux
            # URL qui commencent par REFRESH_PATH — c'est-à-dire à une seule
            # route de toute l'application.
            path=REFRESH_PATH)

    # `and token is None`: le nettoyage ne s'applique que si la requête n'a pas
    # posé de nouveau token. Sans cette condition, un scénario casse la
    # connexion sans rien dire — arriver sur /login avec un vieux cookie
    # invalide (compte désactivé) demande l'effacement, puis le formulaire est
    # validé et pose un cookie neuf, que ce delete_cookie annulerait.
    if getattr(g, G_CLEAR, False) and token is None:
        response.delete_cookie(COOKIE_NAME, path='/')
        # Le `path=` doit être EXACTEMENT celui de la pose. Un `delete_cookie`
        # sur '/' ne supprime pas un cookie posé sur '/auth/refresh': le
        # navigateur les considère comme deux cookies différents, garde le
        # second, et rien dans la réponse ne le laisse voir.
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_PATH)

    return response
