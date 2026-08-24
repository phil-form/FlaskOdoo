# 19 — JWT: authentification par token

Fichiers: `app/services/auth_service_jwt.py`, `app/services/auth_service_impl.py`

Ce chapitre traite du **remplacement** de l'authentification par session
(chapitre 09) par un JWT. Le refresh token, qui est un mécanisme à part, a son
propre chapitre (20).

## Ce que ça change, et ce que ça ne change pas

Le basculement tient en **un décorateur déplacé**:

```python
# auth_service_impl.py  (session)
# @injectable(base=AuthService, scope=Scope.SCOPED)      <- retiré

# auth_service_jwt.py   (JWT)
@injectable(base=AuthService, scope=Scope.SCOPED)        <- posé ici
```

**Aucun controller, aucun template, aucun décorateur `@auth_required` ne change.**
Les vues annotent `auth_service: AuthService` et l'injecteur livre ce que le
décorateur désigne. C'est ce que l'interface du chapitre 09 promettait sans pouvoir
le démontrer, et la meilleure justification qu'on puisse donner à l'injection de
dépendances (chapitre 08).

⚠️ Deux classes décorées avec la même `base` en même temps: la **dernière importée
gagne**, silencieusement (ordre alphabétique des fichiers). Une seule à la fois.

## Session ou token: le tableau honnête

| Critère | Session (chapitre 09) | JWT (ici) |
|---|---|---|
| Où vit l'identité | cookie signé, user rechargé en base | **dans le token** |
| Requêtes SQL pour autoriser | 1 | **0** |
| Révocation immédiate | oui (`session.clear()`) | **impossible** |
| Rôles à jour | immédiatement | à l'expiration du token |
| Rotation de session nécessaire | oui (chapitre 17) | **sans objet** |
| Adapté à | site web classique | API, mobile, plusieurs services |
| État côté serveur | aucun (cookie signé) | aucun |

La ligne qui fait mal est « révocation impossible »: un token volé reste valable
jusqu'à `exp`. Deux réponses possibles: un `exp` court (mais on se reconnecte toutes
les 15 minutes) ou un refresh token — chapitre 20.

La rotation de session devient sans objet parce que l'attaque de *session fixation*
suppose un identifiant de session réutilisable, et il n'y en a plus.

## Où mettre le token: cookie ou en-tête ?

| | `Authorization: Bearer` | Cookie httpOnly |
|---|---|---|
| Pour | une API, un front séparé | un site rendu côté serveur |
| Stockage client | à la charge du JS (`localStorage` = lisible par tout XSS) | le navigateur, invisible au JS |
| Envoi | explicite | **automatique** |
| CSRF | impossible | **possible: protection obligatoire** |

Ce projet étant en MVC, le token va dans un **cookie httpOnly**, `Secure` hors
debug, `SameSite=Lax`. Donc:

> **Le JWT ne dispense pas du CSRF.** L'idée reçue « JWT = plus besoin de CSRF » ne
> vaut que pour un token envoyé à la main dans un en-tête. Dans un cookie, le
> navigateur l'envoie tout seul: `CSRFProtect` (chapitre 06) reste indispensable.
> C'est vérifié par un test.

Les deux modes sont lus, pour qu'un client d'API puisse utiliser les mêmes routes:

```python
entete = request.headers.get('Authorization', '')

if entete.startswith('Bearer '):
    return entete[len('Bearer '):]

return request.cookies.get(COOKIE_NAME)
```

## Les claims

```python
claims = {
    'sub': str(user.user_id),        # standards (RFC 7519)
    'iat': now,
    'exp': now + timedelta(minutes=self.__minutes),
    'username': user.username,       # applicatifs: de quoi autoriser sans SQL
    'email': user.email,
    'email_verified': bool(user.email_verified),
    'roles': user.role_names(),
}
```

Un JWT est **signé, pas chiffré**: son contenu se lit avec un `base64 -d`. N'y
mettez donc jamais de secret — et rappelez-vous que le mot de passe n'y est pas.

`PyJWT` vérifie `exp` tout seul au décodage.

## `algorithms=` n'est pas optionnel

```python
jwt.decode(token, app.config['SECRET_KEY'], algorithms=[self.ALGORITHM])
```

C'est une **liste blanche**. Sans elle, un attaquant présente un token signé avec
l'algorithme `none` et devient administrateur: c'est la faille la plus connue de
l'écosystème JWT. Elle est testée dans le projet (`token alg=none refusé`), ainsi
que la signature falsifiée et la signature avec une autre clé.

Sujet voisin, à connaître: la **confusion d'algorithme** (présenter un token HS256
signé avec la clé publique à un serveur qui attend du RS256). La liste blanche la
bloque aussi.

HS256 (secret partagé) suffit quand un seul service émet et vérifie. Dès que
plusieurs services doivent **vérifier** les tokens, RS256 évite de diffuser le
secret de signature: chacun n'a besoin que de la clé publique.

## Le compromis: des données périmées

Les rôles voyagent dans les claims, donc autoriser ne coûte **aucune requête SQL**
(mesuré: zéro requête pour identifier l'utilisateur sur une page sans données). Le
prix: un rôle retiré reste valable jusqu'à l'expiration.

Exemple concret et gênant dans ce projet: un compte qui confirme son adresse email
garde un token disant `email_verified: false` — bandeau affiché, checkout refusé,
parfois pendant une heure. Le lien de confirmation étant souvent ouvert dans un
**autre navigateur**, on ne peut pas compter sur cette requête pour rafraîchir le
cookie.

La règle retenue:

> **un claim qui autorise doit être soit très court, soit revérifié.**

```python
if not self.__current_user.email_verified:
    frais = self.__user_service.find_one(self.__current_user.user_id)

    if frais is not None and frais.email_verified:
        self.__current_user = frais
        setattr(g, G_SET, self.encode(frais))     # token réémis à jour
```

On relit la base **uniquement quand le claim est défavorable**: une requête pour les
seuls comptes concernés, chemin rapide (zéro SQL) pour tous les autres.

## Poser le cookie depuis un service

Au moment où le controller appelle `login()`, la réponse HTTP n'existe pas encore.
Le service dépose donc le token dans `g`, et un `after_request` écrit le cookie:

```python
@app.after_request
def ecrire_cookie_jwt(response):
    token = getattr(g, G_SET, None)
    if token is not None:
        response.set_cookie(COOKIE_NAME, token, httponly=True, ...)
    ...
```

Ce hook s'enregistre **à l'import du module**, donc via le
`from app.services import *` de `app/__init__.py`: l'implémentation JWT est
autonome, on n'a pas eu à modifier `app/__init__.py` pour elle.

## Le préfixe `__Host-`

```python
COOKIE_NAME = "access_token" if app.debug else "__Host-access_token"
```

Le navigateur refuse un cookie `__Host-` qui ne serait pas `Secure`, ou posé sur un
autre domaine ou chemin. Un sous-domaine compromis ne peut donc plus écrire notre
cookie de token.
