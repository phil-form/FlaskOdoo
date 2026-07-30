# Étape 06 — Authentification et rôles

Jusqu'ici n'importe qui pouvait supprimer le catalogue. On ajoute les comptes, la
connexion, et deux rôles (`USER`, `ADMIN`).

C'est l'étape la plus dense de la formation, et celle où les erreurs coûtent le
plus cher: la moitié du contenu ci-dessous concerne des pièges de sécurité.

---

## Démarrer

```bash
docker compose up -d db-example
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py
```

`/seed`, puis connectez-vous:

| Utilisateur | Mot de passe | Rôles |
|---|---|---|
| `admin` | `admin` | USER, ADMIN |
| `test` | `test` | USER |

Comparez la barre de navigation et les boutons du catalogue selon le compte.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/services/user_service.py` | comptes, hachage argon2, inscription, connexion |
| `app/services/role_service.py` | lecture des rôles (créés par le seed) |
| `app/services/auth_service.py` | **l'interface**: qui est connecté ? |
| `app/services/auth_service_impl.py` | l'implémentation « session Flask » |
| `app/framework/decorators/auth_required.py` | `@auth_required(level=..., or_is_current_user=...)` |
| `app/dtos/user_dto.py`, `role_dto.py`, `app/mappers/user_mapper.py` | transport, sans le mot de passe |
| `app/forms/user/*.py` | connexion, inscription, modification de profil |
| `app/controllers/user_controller.py` | login, logout, register, profils, administration |
| `app/templates/users/*.html` | les pages correspondantes |
| `app/__init__.py` | + un `context_processor` qui expose `current_user` |
| `app/controllers/item_controller.py` | les routes d'écriture passent en ADMIN |

### 1. Le mot de passe: hacher, jamais chiffrer

```python
self.__hasher = PasswordHasher()                     # argon2
user.password = self.__hasher.hash(user.password)    # inscription
self.__hasher.verify(user.password, candidate)       # connexion
```

- **Jamais de mot de passe en clair**, même en développement, même dans les
  seeds.
- **Pas de MD5/SHA-256**: ces fonctions sont *rapides*, donc parfaites pour
  tester des milliards de candidats. Il faut un algorithme lent et paramétrable:
  argon2, bcrypt, scrypt.
- Le **sel est inclus** dans la chaîne produite par argon2: pas de colonne
  `salt`. Deux utilisateurs avec le même mot de passe ont des hash différents.
- `verify()` **lève une exception**, il ne renvoie pas `False`.

Deux détails du login qui n'en sont pas:

```python
if user is None:
    self.__hasher.hash(candidate.password)   # égalise le temps de réponse
    return None
```

Sans ce hachage à vide, répondre en 1 ms (compte inconnu) contre 50 ms (mot de
passe faux) révèle quels comptes existent — c'est une *timing attack*. Et le
message d'erreur est toujours le même: « utilisateur ou mot de passe incorrect ».

### 2. `AuthService`: une interface pour un seul point de variation

```python
@injectable(base=AuthService, scope=Scope.SCOPED)
class AuthServiceImpl(AuthService):
```

- `base=AuthService`: les vues annotent **l'interface**, l'injecteur livre
  l'implémentation. Pour passer à une authentification par token JWT: écrire
  `AuthServiceJwt`, y déplacer le décorateur. Rien d'autre.
- `scope=SCOPED`: une instance par requête (voir étape 05).

La session ne contient que l'`user_id`; l'utilisateur est **rechargé depuis la
base** à chaque requête, en *lazy* (aucune requête SQL sur une page publique).
Conséquence utile: un rôle retiré prend effet immédiatement, sans attendre la
déconnexion.

La session Flask est un cookie **signé** avec `SECRET_KEY`: le client peut le
lire, pas le modifier. Ce n'est pas du chiffrement — n'y mettez rien de
confidentiel.

### 3. `@auth_required`

```python
@app.get('/users')
@auth_required(level="ADMIN")
@inject
def user_list(user_service: UserService): ...
```

```python
if current_user is None:                       # pas connecté
    return redirect(url_for('login', next=request.path))

if "ADMIN" in roles:                           # 1. un ADMIN passe partout
    return func(*args, **kwargs)

if level is not None and level in roles:       # 2. le rôle demandé
    return func(*args, **kwargs)

if or_is_current_user and current_user.user_id == kwargs.get('user_id'):
    return func(*args, **kwargs)               # 3. sa propre ressource

if level is None and not or_is_current_user:   # connecté suffit
    return func(*args, **kwargs)
```

Trois écritures, trois intentions:

```python
@auth_required()                          # être connecté suffit
@auth_required(level="ADMIN")             # rôle exigé
@auth_required(or_is_current_user=True)   # le propriétaire, ou un ADMIN
```

**Deux configurations dangereuses sont refusées au démarrage** (pas au moment
d'une requête), parce qu'elles seraient silencieusement fausses:

- `or_is_current_user=True` sur une vue **sans paramètre `user_id`** — la règle de
  propriété ne pourrait jamais s'appliquer;
- `level="USER"` **avec** `or_is_current_user=True` — tous les comptes ont le rôle
  USER, donc la ressource serait ouverte à tous et la règle de propriété inutile.

Le second cas était un vrai piège de la première version du décorateur: n'importe
qui pouvait éditer le profil de n'importe qui. Plutôt que de le documenter, on l'a
rendu **impossible**: le décorateur lève un `ValueError` à la déclaration de la
vue. C'est le bon réflexe — une API qui empêche l'erreur vaut mieux qu'un
avertissement dans un README.

### 4. Cacher n'est pas protéger

Le layout masque les liens d'administration:

```jinja
{% if current_user and current_user.is_admin() %}
    <a href="{{ url_for('user_list') }}">Utilisateurs</a>
{% endif %}
```

C'est du confort. La sécurité, c'est `@auth_required(level="ADMIN")` sur la vue:
rien n'empêche de taper l'URL.

Même raisonnement pour le champ « rôles » du formulaire de profil: masqué aux
non-admins dans le template, mais **revérifié** dans le controller:

```python
if current_user.is_admin():
    user_service.update_roles(user_id, form.selected_roles())
```

Un champ absent du HTML peut toujours être envoyé à la main. C'est l'exercice 3.

### 5. `?next=` et la redirection ouverte

```python
next_page = request.args.get('next')
if next_page and next_page.startswith('/'):     # <- la vérification
    return redirect(next_page)
```

Sans le test, `/login?next=https://site-pirate` ferait de votre application un
tremplin crédible pour du phishing.

### 6. `current_user` partout

```python
@app.context_processor
def inject_current_user():
    auth_service = app.injector[AuthService.__name__]
    return {'current_user': auth_service.get_current_user()}
```

Un *context processor* est appelé avant chaque rendu, et son dictionnaire est
fusionné avec les variables du template. Ça évite de passer `current_user=...`
dans les quinze `render_template` du projet.

---

## Exercices

### 1. Voir la session

- Connectez-vous, ouvrez les outils de développement → Application → Cookies.
  Regardez le cookie `session`: il est lisible mais signé.
- Modifiez un caractère de sa valeur, rechargez. Que se passe-t-il ?
- Changez `SECRET_KEY` dans `.env.local`, relancez le serveur, rechargez la page.
  Expliquez.

### 2. Le piège `or_is_current_user`

Dans `user_controller.py`, remplacez
`@auth_required(level="ADMIN", or_is_current_user=True)` par
`@auth_required(or_is_current_user=True)`.

- Connecté en `test`, essayez d'ouvrir `/users/1/edit` (le profil de `admin`).
- Que se passe-t-il ? Pourquoi ? Remettez le code d'origine.
- Écrivez le test automatique qui aurait attrapé ce bug.

### 3. Tenter une escalade de privilèges

Connecté en `test` (rôle USER), postez le formulaire de votre profil **en y
ajoutant** le champ des rôles, par exemple avec les outils de développement ou:

```bash
curl -X POST http://localhost:8080/users/2/edit \
     -d "email=test@example.com&description=hop&roles=2&csrf_token=<le jeton>"
```

- Le rôle est-il attribué ? Où est-ce bloqué, exactement ?
- Que se passerait-il si le controller faisait confiance au formulaire ?

### 4. Le hachage

```python
from argon2 import PasswordHasher
ph = PasswordHasher()
print(ph.hash("admin"))
print(ph.hash("admin"))      # deux fois: comparez
```

- Pourquoi les deux chaînes diffèrent-elles ? Où est le sel ?
- Mesurez le temps d'un `hash()` (`time.perf_counter`). Pourquoi est-ce une
  bonne nouvelle qu'il soit « lent » ?
- Que renvoie `verify()` avec un mauvais mot de passe ?

### 5. Un rôle intermédiaire

Ajoutez un rôle `MANAGER` qui peut créer et modifier des articles, mais pas les
supprimer ni gérer les utilisateurs.

1. dans `RoleSeed`;
2. sur les décorateurs de `item_controller.py`;
3. relisez la règle « un ADMIN passe partout » du décorateur: pourquoi est-elle
   là ?
4. Accepter une **liste** (`level=["MANAGER", "ADMIN"]`) serait-il plus clair ?
   Implémentez-le.

### 6. Ce qui manque encore

Listez ce qui empêcherait de mettre cette application en production côté
authentification. (Comparez ensuite avec la section « Ce que le projet ne fait pas »
de `../09-projet-final/docs/09-authentification.md`.) Une de ces briques est
ajoutée à l'étape 08.

---

## Pour aller plus loin

`../09-projet-final/docs/09-authentification.md`

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`07-panier-et-commande`](../07-panier-et-commande/) — le panier, les quantités,
la validation de commande et les stocks.
