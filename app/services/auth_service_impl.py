from flask import session

from app.dtos.user_dto import UserDTO
from app.framework.decorators.inject import inject
from app.framework.decorators.injectable import injectable
from app.framework.injector import Scope
from app.services.auth_service import AuthService
from app.services.user_service import UserService


# base=AuthService: les vues annotent `auth_service: AuthService` (l'interface),
# c'est donc sous ce nom qu'il faut s'enregistrer. Changer d'implémentation
# (un AuthServiceJwt, par exemple) = déplacer ce décorateur, rien d'autre.
#
# scope=SCOPED: ce service mémorise l'utilisateur courant. En SINGLETON, le
# premier visiteur imposerait son identité à tous les suivants.
# @injectable RETIRÉ à cette étape: c'est AuthServiceJwt qui est désormais
# enregistré comme implémentation de AuthService (voir auth_service_jwt.py).
#
# Le fichier est conservé volontairement: comparer les deux implémentations côte
# à côte est plus parlant qu'un `git log`. Pour revenir à la session, il suffit
# de déplacer le décorateur — et rien d'autre ne change dans l'application.
#
# Attention: deux classes décorées avec base=AuthService en même temps, et la
# dernière importée gagne, silencieusement (ordre alphabétique des fichiers).
# Une seule à la fois.
#
# @injectable(base=AuthService, scope=Scope.SCOPED)
class AuthServiceImpl(AuthService):
    """Implémentation "site web": l'identité vit dans la session Flask.

    La session Flask est un cookie SIGNÉ avec app.secret_key. Le client peut
    donc le lire mais pas le forger: modifier un octet invalide la signature et
    Flask jette la session. On y met malgré tout le strict minimum (l'id), et on
    recharge l'utilisateur depuis la base à chaque requête — comme ça un rôle
    retiré prend effet immédiatement au lieu d'attendre la déconnexion.

    Ce service est enregistré en Scope.SCOPED: une instance par requête HTTP.
    Le user est donc chargé une seule fois par requête, même si dix vues ou
    templates le demandent.
    """

    @inject
    def __init__(self, user_service: UserService):
        # @inject sur __init__: l'injecteur fournit user_service, on peut donc
        # écrire AuthServiceImpl() sans argument — ce que fait l'injecteur quand
        # une vue demande AuthService.
        self.__user_service = user_service
        self.__current_user: UserDTO | None = None
        self.__loaded = False

    def get_current_user(self) -> UserDTO | None:
        # Chargement paresseux: une page publique ne fait aucune requête SQL
        # pour l'utilisateur si elle n'en a pas besoin.
        if not self.__loaded:
            self.__loaded = True
            user_id = session.get('user_id')

            if user_id is not None:
                self.__current_user = self.__user_service.find_one(user_id)

                # Compte supprimé/désactivé entre-temps: on nettoie la session.
                if self.__current_user is None:
                    session.pop('user_id', None)

        return self.__current_user

    def login(self, user: UserDTO):
        # ROTATION DE SESSION. Attaque évitée: la « session fixation ».
        # Un attaquant vous fait utiliser un identifiant de session qu'il connaît
        # (lien piégé, cookie injecté par un sous-domaine, XSS ailleurs sur le
        # domaine). Vous vous connectez... et il possède maintenant une session
        # authentifiée: c'est la VÔTRE.
        #
        # La parade est toujours la même: à l'élévation de privilège (connexion),
        # on repart d'une session vierge. Flask ne donne pas de
        # "regenerate_id()" — sa session vit entièrement dans le cookie signé —
        # mais session.clear() a le même effet utile: tout ce que la session
        # contenait avant la connexion est jeté, et le cookie renvoyé est
        # nouveau.
        #
        # À faire aussi lors d'un changement de mot de passe, ou d'un passage en
        # administrateur.
        session.clear()

        session['user_id'] = user.user_id
        # permanent = la session survit à la fermeture du navigateur
        # (durée réglée par app.permanent_session_lifetime).
        session.permanent = True
        self.__current_user = user
        self.__loaded = True

    def logout(self):
        session.clear()
        self.__current_user = None
        self.__loaded = True

    def is_authenticated(self) -> bool:
        return self.get_current_user() is not None
