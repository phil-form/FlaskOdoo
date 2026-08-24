import os
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, request

from app import app
from app.dtos.role_dto import RoleDTO
from app.dtos.user_dto import UserDTO
from app.framework.decorators.inject import inject
from app.framework.decorators.injectable import injectable
from app.framework.injector import Scope
from app.services.auth_service import AuthService
from app.services.user_service import UserService

# Nom du cookie qui transporte le token. Le préfixe __Host- (production) fait
# refuser par le navigateur tout cookie qui ne serait pas Secure, ou posé sur un
# autre domaine/chemin: un sous-domaine compromis ne peut plus écrire le nôtre.
COOKIE_NAME = "access_token" if app.debug else "__Host-access_token"

# Clés de `g` utilisées pour communiquer avec le after_request en bas de fichier.
G_SET = '_jwt_a_poser'
G_CLEAR = '_jwt_a_supprimer'


@injectable(base=AuthService, scope=Scope.SCOPED)
class AuthServiceJwt(AuthService):
    """Authentification par JWT, à la place de la session Flask.

    Ce qui change par rapport à AuthServiceImpl:

    - l'identité ne vit plus côté serveur, elle est **dans le token**, signé;
    - il n'y a plus d'état de session à faire tourner, ce qui rend la « rotation
      de session » de l'étape 12 sans objet: l'attaque de session fixation
      suppose un identifiant de session réutilisable, et il n'y en a plus;
    - les rôles voyagent dans les claims, donc `@auth_required` n'a plus besoin
      d'une requête SQL. En contrepartie, un rôle retiré reste valable jusqu'à
      l'expiration du token: c'est LE compromis du JWT.

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
    def __init__(self, user_service: UserService):
        self.__user_service = user_service
        self.__minutes = int(os.environ.get("JWT_ACCESS_MINUTES", 60))
        self.__current_user: UserDTO | None = None
        self.__loaded = False

    # --- lecture ------------------------------------------------------------

    def get_current_user(self) -> UserDTO | None:
        if self.__loaded:
            return self.__current_user

        self.__loaded = True
        token = self.read_token()

        if token is None:
            return None

        claims = self.decode(token)

        if claims is None:
            return None

        # Reconstruit un UserDTO à partir des seuls claims: AUCUNE requête SQL.
        # C'est tout l'intérêt du JWT — et sa limite (données périmables).
        self.__current_user = self.dto_from_claims(claims)

        # --- LA LIMITE DU JWT, ET COMMENT LA TRAITER ------------------------
        # Un claim est une PHOTO prise à l'émission du token. Ici, un compte qui
        # confirme son adresse garde un token qui dit `email_verified: false`:
        # le bandeau reste affiché et le checkout reste refusé, parfois pendant
        # une heure. Le lien de confirmation est souvent ouvert dans un AUTRE
        # navigateur, on ne peut donc pas compter sur la réponse de cette
        # requête-là pour rafraîchir le cookie.
        #
        # Règle à retenir: un claim qui AUTORISE doit être soit très court, soit
        # revérifié. On relit donc la base — mais uniquement quand le claim est
        # défavorable: si le token dit « vérifié », il n'y a rien à gagner à
        # requêter, et on garde le chemin rapide (zéro SQL) pour la quasi-totalité
        # des requêtes.
        if not self.__current_user.email_verified:
            frais = self.__user_service.find_one(self.__current_user.user_id)

            if frais is not None and frais.email_verified:
                self.__current_user = frais
                # Le token est réémis à jour: les requêtes suivantes repassent
                # par le chemin rapide.
                setattr(g, G_SET, self.encode(frais))

        return self.__current_user

    def is_authenticated(self) -> bool:
        return self.get_current_user() is not None

    # --- écriture -----------------------------------------------------------

    def login(self, user: UserDTO):
        # On ne stocke rien: on demande au after_request de poser le cookie. Le
        # service ne manipule pas la réponse lui-même — au moment où le
        # controller appelle login(), la réponse n'existe pas encore.
        setattr(g, G_SET, self.encode(user))
        self.__current_user = user
        self.__loaded = True

    def logout(self):
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
            # Claims applicatifs: de quoi autoriser sans toucher la base.
            'username': user.username,
            'email_verified': bool(user.email_verified),
            'roles': user.role_names(),
        }

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

    def dto_from_claims(self, claims: dict) -> UserDTO:
        # Attention qu'on ne fait généralement pas confience aux données du token (elles peuvent expiré
        # -> modification en db).
        # Un token peut aussi être forgé -> donc maintenez les algorithmes de signature à jours !
        #   -> regarder la doc de l'owasp
        #   -> avoir des passkey sécirusé et pas simple à craquer.
        user_id = int(claims['sub'])
        user = self.__user_service.find_one(user_id)

        return user


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

    if getattr(g, G_CLEAR, False):
        response.delete_cookie(COOKIE_NAME, path='/')

    return response
