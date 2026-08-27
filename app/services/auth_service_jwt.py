import os
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, request

from app import app
from app.dtos.user_dto import UserDTO
from app.framework.decorators.inject import inject
from app.framework.decorators.injectable import injectable
from app.framework.injector import Scope
from app.services.auth_service import AuthService
from app.services.refresh_token_service import RefreshTokenService
from app.services.user_service import UserService

# Nom du cookie qui transporte le token. Le préfixe __Host- (production) fait
# refuser par le navigateur tout cookie qui ne serait pas Secure, ou posé sur un
# autre domaine/chemin: un sous-domaine compromis ne peut plus écrire le nôtre.
COOKIE_NAME = "access_token" if app.debug else "__Host-access_token"
REFRESH_COOKIE_NAME = "refresh_token" if app.debug else "__Host-refresh_token"

# Clés de `g` utilisées pour communiquer avec le after_request en bas de fichier.
G_SET = '_jwt_a_poser'
G_CLEAR = '_jwt_a_supprimer'
G_REFRESH_SET = '_refresh_a_poser'


@injectable(base=AuthService, scope=Scope.SCOPED)
class AuthServiceJwt(AuthService):
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

    Où mettre le token ? Deux écoles:

    - **en-tête** `Authorization: Bearer ...` — pour une API. Le client doit le
      stocker quelque part (localStorage: lisible par n'importe quel XSS).
    - **cookie httpOnly** — pour un site rendu côté serveur, notre cas: le
      navigateur l'envoie tout seul et le JavaScript ne peut pas le lire. Mais un
      cookie part automatiquement, donc la protection **CSRF reste
      indispensable**. C'est l'erreur classique: « je suis passé au JWT, je n'ai
      plus besoin de CSRF » — faux dès que le token est dans un cookie.

    Les deux sont lus ici: le cookie pour les pages, l'en-tête pour qu'un client
    d'API puisse utiliser les mêmes routes.
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
            # Access token absent, expiré ou invalide: on tente le renouvellement
            # silencieux avec le refresh token. L'utilisateur ne voit rien — il ne
            # sait même pas que son access token vivait 15 minutes.
            claims = self.__renouveler()

        if claims is None:
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
        # `UserService.find_one_entity` (étape 19) — une requête indexée, deux
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

    def __renouveler(self) -> dict | None:
        """Échange le refresh token contre un nouvel access token (rotation).

        Deux règles importantes:

        1. **rotation**: le refresh token est consommé et remplacé. Un token qui
           resterait valable des jours entiers après usage serait aussi dangereux
           qu'un mot de passe volé.
        2. **rechargement depuis la base**: on relit le compte pour vérifier
           qu'il existe encore avant d'émettre un nouvel access token. Depuis
           que `get_current_user` relit la base à chaque requête, ce n'est plus
           ici que se joue la fraîcheur des droits — mais ça reste le bon
           endroit pour refuser de renouveler le token d'un compte disparu.
        """
        refresh = request.cookies.get(REFRESH_COOKIE_NAME)

        if not refresh:
            return None

        resultat = self.__refresh_token_service.rotate(refresh)

        if resultat is None:
            # Inconnu, expiré, ou rejeu (la famille vient d'être révoquée):
            # on efface les cookies pour forcer une vraie reconnexion.
            setattr(g, G_CLEAR, True)
            return None

        user_id, nouveau_refresh = resultat
        user = self.__user_service.find_one(user_id)

        if user is None:
            # Compte supprimé ou désactivé entre-temps: on ne renouvelle pas.
            setattr(g, G_CLEAR, True)
            return None

        app.logger.debug(f"jwt: access token renouvelé pour {user.username}")

        setattr(g, G_SET, self.encode(user))
        setattr(g, G_REFRESH_SET, nouveau_refresh)

        return self.decode(getattr(g, G_SET))

    def login(self, user: UserDTO):
        # On ne stocke rien: on demande au after_request de poser le cookie. Le
        # service ne manipule pas la réponse lui-même — au moment où le
        # controller appelle login(), la réponse n'existe pas encore.
        setattr(g, G_SET, self.encode(user))
        # Une connexion = une nouvelle FAMILLE de refresh tokens. Les familles
        # précédentes restent valables: se connecter sur son téléphone ne doit pas
        # déconnecter l'ordinateur.
        setattr(g, G_REFRESH_SET, self.__refresh_token_service.issue(user.user_id))
        self.__current_user = user
        self.__loaded = True

    def logout(self):
        # Révoquer côté serveur: supprimer le cookie ne suffirait pas, une copie
        # du refresh token continuerait de fonctionner pendant des jours.
        refresh = request.cookies.get(REFRESH_COOKIE_NAME)

        if refresh:
            self.__refresh_token_service.revoke(refresh)

        setattr(g, G_CLEAR, True)
        self.__current_user = None
        self.__loaded = True

    # --- token --------------------------------------------------------------

    def encode(self, user: UserDTO) -> str:
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


@app.after_request
def ecrire_cookie_jwt(response):
    """Pose ou supprime le cookie du token, selon ce que la vue a demandé.

    Ce hook s'enregistre à l'import du module — donc via le
    `from app.services import *` de app/__init__.py. L'implémentation JWT est
    autonome: on n'a pas eu à modifier app/__init__.py pour elle.
    """
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
            # Le cookie meurt avec le token: garder un token expiré ne sert à rien
            max_age=int(os.environ.get("JWT_ACCESS_MINUTES", 60)) * 60,
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
            path='/')

    # `and token is None`: le nettoyage ne s'applique que si la requête n'a pas
    # posé de nouveau token. Sans cette condition, un scénario casse la
    # connexion sans rien dire — arriver sur /login avec un vieux cookie
    # invalide (compte désactivé) demande l'effacement, puis le formulaire est
    # validé et pose un cookie neuf, que ce delete_cookie annulerait.
    if getattr(g, G_CLEAR, False) and token is None:
        response.delete_cookie(COOKIE_NAME, path='/')
        response.delete_cookie(REFRESH_COOKIE_NAME, path='/')

    return response
