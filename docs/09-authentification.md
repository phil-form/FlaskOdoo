# 09 — Authentification & rôles

> **Authentification par token**: ce chapitre décrit l'authentification par
> **session** (cookie signé côté serveur). Le passage au JWT est un sujet à part
> entière, traité dans son propre chapitre — voir `19-jwt.md` et
> `20-jwt-refresh-token.md` quand ils sont présents (étapes 14 et 15 de la
> formation).

Fichiers: `app/services/auth_service*.py`,
`app/framework/decorators/auth_required.py`, `app/models/role.py`,
`app/models/user_role.py`

## Session ou token ?

| | Session (ce projet) | JWT (version API) |
|---|---|---|
| Stockage | cookie signé, envoyé automatiquement | en-tête `Authorization`, géré par le client |
| Contenu | juste `user_id` | les données du user + expiration |
| Révocation | immédiate (`session.clear()`) | difficile: le token reste valide jusqu'à expiration |
| Adapté à | site web classique | API, mobile, front séparé |

Un site MVC utilise la session: le navigateur envoie le cookie tout seul, et
c'est ce qui permet à `{% if current_user %}` de fonctionner dans le layout.

La session Flask est un cookie **signé** avec `SECRET_KEY`: le client peut le
lire mais pas le modifier (la signature ne suivrait pas). Ce n'est pas du
chiffrement — n'y mettez rien de confidentiel.

## AuthService

```python
class AuthService(ABC):
    def get_current_user(self) -> UserDTO | None: ...
    def login(self, user: UserDTO): ...
    def logout(self): ...
    def is_authenticated(self) -> bool: ...
```

L'implémentation met le strict minimum en session et **recharge le user depuis la
base** à chaque requête:

```python
def get_current_user(self):
    if not self.__loaded:
        self.__loaded = True
        user_id = session.get('user_id')
        if user_id is not None:
            self.__current_user = self.__user_service.find_one(user_id)
            if self.__current_user is None:       # compte supprimé entre-temps
                session.pop('user_id', None)
    return self.__current_user
```

Pourquoi recharger plutôt que stocker les rôles dans le cookie? Parce qu'un rôle
retiré prendrait effet seulement à la prochaine connexion. Ici, l'effet est
immédiat. Le coût — une requête SQL par requête HTTP — est acceptable, et le
chargement paresseux fait qu'une page publique n'en fait aucune.

Le service est en `Scope.SCOPED`: une instance par requête, donc le user n'est
chargé qu'une fois même si dix vues et templates le demandent.

## Le hachage des mots de passe

```python
self.__hasher = PasswordHasher()                    # argon2
user.password = self.__hasher.hash(user.password)    # à l'inscription
self.__hasher.verify(user.password, candidate)       # à la connexion
```

Points essentiels:

- **Jamais de mot de passe en clair en base**, même en développement, même dans
  les seeds. Une fuite de base ne doit pas être une fuite de mots de passe (et
  les gens réutilisent les leurs ailleurs).
- **Pas de MD5/SHA1/SHA256**: ces fonctions sont *rapides*, donc parfaites pour
  tester des milliards de candidats. Il faut un algorithme **lent et paramétrable**:
  argon2 (recommandé), bcrypt, scrypt.
- **Le sel est inclus** dans la chaîne produite par argon2: pas de colonne `salt`
  à gérer. Deux utilisateurs avec le même mot de passe ont des hash différents.
- `verify()` **lève une exception** en cas de non-correspondance, il ne renvoie
  pas `False`:

```python
try:
    self.__hasher.verify(user.password, candidate.password)
except (VerifyMismatchError, VerificationError, InvalidHashError):
    return None
```

- `check_needs_rehash()` permet de remettre à niveau un hash produit avec des
  paramètres devenus trop faibles, pendant qu'on a le mot de passe en clair:

```python
if self.__hasher.check_needs_rehash(user.password):
    user.password = self.__hasher.hash(candidate.password)
    db.session.commit()
```

### Deux détails de login qui n'en sont pas

**Message d'erreur unique.** « Utilisateur ou mot de passe incorrect », jamais
« cet utilisateur n'existe pas ». Sinon on offre un moyen d'énumérer les comptes
existants.

**Temps de réponse constant.** Si l'utilisateur est inconnu, on hashe quand même
dans le vide:

```python
if user is None:
    self.__hasher.hash(candidate.password)   # égalise le temps de réponse
    return None
```

Sans ça, une réponse en 1 ms (compte inconnu) contre 50 ms (mot de passe faux)
révèle quels comptes existent. C'est une *timing attack*, et c'est mesurable même
sur un réseau.

## Les rôles

Modèle: `User` --(`UserRole`)-- `Role`, many-to-many (voir
[03-modeles-et-relations.md](03-modeles-et-relations.md)). Deux rôles créés par
`RoleSeed`: `USER` et `ADMIN`.

Côté entité:

```python
user.add_role(role)      # sans doublon
user.remove_role(role)
user.role_names()        # ['USER', 'ADMIN']
user.is_admin()
```

Côté DTO (ce que voient les templates): `current_user.role_names()`,
`current_user.is_admin()`.

## Le décorateur @auth_required

```python
@app.get('/users')
@auth_required(level="ADMIN")
@inject
def user_list(user_service: UserService): ...
```

Trois écritures, trois intentions:

```python
@auth_required()                          # être connecté suffit
@auth_required(level="ADMIN")             # rôle exigé
@auth_required(or_is_current_user=True)   # le propriétaire, ou un ADMIN
```

Son fonctionnement, dans cet ordre:

```python
current_user = auth_service.get_current_user()

if current_user is None:                        # pas connecté
    flash("Veuillez vous connecter...", "warning")
    return redirect(url_for('login', next=request.path))

roles = current_user.role_names()

if "ADMIN" in roles:                            # 1. un ADMIN passe partout
    return func(*args, **kwargs)

if level is not None and level in roles:        # 2. le rôle demandé
    return func(*args, **kwargs)

if or_is_current_user and current_user.user_id == kwargs.get('user_id'):
    return func(*args, **kwargs)                # 3. sa propre ressource

if level is None and not or_is_current_user:    # aucune exigence: connecté suffit
    return func(*args, **kwargs)

flash("Vous n'avez pas les droits nécessaires.", "danger")
return redirect(url_for('index'))
```

`level=None` par défaut se lit « aucun rôle particulier exigé ». La règle ADMIN
est en premier: sans elle, il faudrait penser à donner à chaque administrateur
tous les autres rôles.

C'est un **décorateur à paramètres**, donc trois niveaux de fonctions
imbriquées:

```python
def auth_required(level=None, or_is_current_user=False):     # reçoit les options
    def auth_required_decorator(func):                       # reçoit la vue
        ...                                                  # garde-fous ICI, au démarrage
        @wraps(func)
        @inject
        def function_wrapper(*args, auth_service: AuthService, **kwargs):
            ...                                              # exécuté à chaque requête
        return function_wrapper
    return auth_required_decorator
```

Le niveau du milieu n'est exécuté qu'**une fois par vue**, au chargement du
module: c'est là qu'on place les vérifications de configuration (voir plus bas).
Le niveau du dessous tourne à chaque requête — il n'y a rien à y valider qui ne
change pas.

### `or_is_current_user`: propriétaire ou ADMIN

```python
@auth_required(or_is_current_user=True)
def user_update(user_id, ...):
```

Se lit: « le propriétaire de la ressource, ou un ADMIN » (règle 1: un ADMIN passe
partout). `level` reste à `None`, c'est-à-dire « aucun rôle particulier exigé ».

Deux configurations dangereuses sont **refusées au démarrage** de l'application,
pas au moment d'une requête:

- `or_is_current_user=True` sur une vue **sans paramètre `user_id`**: la règle de
  propriété ne pourrait jamais s'appliquer, et l'accès se dégraderait
  silencieusement en « admin seulement »;
- `level="USER"` **avec** `or_is_current_user=True`: tous les comptes ont le rôle
  USER, la ressource serait donc ouverte à tous et la règle de propriété
  inutile.

C'est le principe à retenir: une API qui **rend l'erreur impossible** vaut mieux
qu'une documentation qui met en garde contre elle. Les deux cas lèvent un
`ValueError` explicite à la déclaration de la vue.

## Cacher ≠ protéger

Le layout masque les liens d'administration:

```jinja
{% if current_user and current_user.is_admin() %}
    <a href="{{ url_for('user_list') }}">Utilisateurs</a>
{% endif %}
```

C'est du confort. La sécurité, c'est `@auth_required(level="ADMIN")` sur la vue:
rien n'empêche quelqu'un de taper l'URL directement.

Même raisonnement pour le champ « rôles » du formulaire de profil: masqué dans le
template pour les non-admins, mais **revérifié** dans le controller
(`if current_user.is_admin(): user_service.update_roles(...)`). Un champ caché ou
absent du HTML peut toujours être envoyé à la main.

## La redirection ?next=

```python
return redirect(url_for('login', next=request.path))   # dans @auth_required
```

puis, après connexion:

```python
next_page = request.args.get('next')
if next_page and next_page.startswith('/'):     # ← la vérification indispensable
    return redirect(next_page)
return redirect(url_for('index'))
```

Le test `startswith('/')` empêche la **redirection ouverte**: sans lui,
`/login?next=https://site-pirate.example` ferait de votre application un tremplin
crédible pour du phishing (« le lien commençait bien par votre-app.com… »).

## Mot de passe oublié

Fichiers: `app/services/password_reset_service.py`,
`app/services/mail_service.py`, `app/forms/user/user_forgot_password_form.py`,
`app/forms/user/user_reset_password_form.py`,
`app/templates/emails/password_reset.txt`

Le parcours complet:

```
1. GET  /password/forgot           l'utilisateur donne son adresse
2. POST /password/forgot           -> PasswordResetService.send_reset_link()
                                      -> token signé + mail via MailService
3.      le mail arrive dans Mailpit (http://localhost:8025 en développement)
4. GET  /password/reset/<token>    token vérifié -> formulaire de nouveau mdp
5. POST /password/reset/<token>    token REvérifié -> UserService.update_password()
6.      redirection vers /login
```

### Le token, sans table supplémentaire

Aucune table `password_resets`: tout est dans le token, signé avec `SECRET_KEY`
par `itsdangerous` — la bibliothèque qui signe déjà les cookies de session de
Flask, donc déjà installée.

```python
self.__serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'],
                                           salt='password-reset')

token = self.__serializer.dumps({
    'user_id': user.user_id,
    'fingerprint': self.__fingerprint(user.password),
})
```

Trois protections, à comprendre ensemble:

| Protection | Mécanisme | Ce que ça empêche |
|---|---|---|
| Intégrité | signature HMAC (`BadSignature`) | fabriquer ou modifier un token (changer le `user_id`!) |
| Expiration | `URLSafeTimedSerializer` + `max_age` | réutiliser un vieux lien (1h par défaut) |
| Usage unique | empreinte du hash de mot de passe | rejouer un lien resté dans une boîte mail |

L'usage unique mérite un mot: le token embarque un `sha256` tronqué du hash de
mot de passe **courant**. Dès que le mot de passe change, l'empreinte recalculée
ne correspond plus et le lien devient inutilisable — on obtient donc l'usage
unique sans stocker quoi que ce soit. Le `salt` sépare les usages: un token de
réinitialisation ne sera jamais accepté là où on attend un autre type de token,
même clé secrète.

La comparaison se fait avec `secrets.compare_digest()` et non `==`: temps
constant, elle ne laisse pas deviner la valeur attendue.

### Pas d'énumération de comptes

```python
password_reset_service.send_reset_link(form.email.data)   # retour ignoré

flash("Si un compte existe pour cette adresse, un lien de "
      "réinitialisation vient d'être envoyé.", "info")
```

Le message est **identique** que l'adresse existe ou non — sinon la page devient
un outil pour savoir qui a un compte sur le site. Même raison que le message
unique du login. Un compte désactivé (soft delete) ne reçoit rien non plus.

### Mailpit: un serveur SMTP bouchon

```yaml
  mailpit:
    image: axllent/mailpit:latest
    ports:
      - '1025:1025'   # SMTP: là où l'application dépose ses mails
      - '8025:8025'   # interface web: http://localhost:8025
```

Mailpit accepte tous les mails et **n'en envoie aucun**: il les garde et les
affiche dans une interface web. C'est la bonne façon de travailler sur des
envois: aucun risque d'écrire à un vrai destinataire, aucun compte SMTP à
configurer, et on relit le contenu exact reçu (y compris les en-têtes).

`MailService` utilise `smtplib` de la bibliothèque standard — aucune dépendance
ajoutée — et retourne `False` au lieu de lever si le serveur est absent: un SMTP
en panne ne doit pas transformer la page en erreur 500.

En production, les mêmes variables pointent vers un vrai serveur:
`MAIL_HOST`, `MAIL_PORT`, `MAIL_USE_TLS=True`, `MAIL_USERNAME`, `MAIL_PASSWORD`.

### Les règles de mot de passe changent selon l'environnement

`app/forms/user/user_register_form.py`:

```python
PASSWORD_VALIDATORS = (
    [DataRequired(), Length(min=4, max=128)]                    # DEBUG
    if app.debug else
    [DataRequired(), Length(min=12, max=128),                   # PRODUCTION
     Regexp(r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', message="...")]
)
```

Une ternaire évaluée une fois à l'import: en formation on tape « admin »
cinquante fois par jour, exiger 12 caractères serait absurde; en production
l'inverse est vrai. Le formulaire de réinitialisation importe la même liste — il
serait dommage de durcir une porte et de laisser l'autre ouverte.

Les `(?=...)` sont des *lookahead*: ils vérifient la présence d'une minuscule,
d'une majuscule et d'un chiffre sans consommer de caractère (`Regexp` utilise
`re.match`).

## Ce que le projet ne fait pas

À connaître, pour ne pas croire l'application complète:

> Plusieurs points de cette liste sont traités par les chapitres 15 à 18
> (limitation des tentatives et du débit, cookies et HTTPS, WAF, JWT). Ce qui
> reste ci-dessous n'est pas fait dans le projet.
- **pas de vérification d'adresse email à l'inscription** — n'importe qui peut
  s'inscrire avec l'adresse de quelqu'un d'autre. Le mécanisme serait le même que
  celui du mot de passe oublié: un token signé envoyé par mail.
- **pas de journal d'audit** des actions d'administration.

Pour un vrai projet, `Flask-Login` (sessions) ou `Flask-Security-Too` (le reste)
apportent ces briques déjà testées. Le code ici est volontairement écrit à la
main pour que le mécanisme soit visible.
