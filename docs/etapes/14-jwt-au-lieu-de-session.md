# Étape 14 — JWT au lieu de session

On remplace la session Flask par un **JWT**. C'est l'étape qui paie l'interface
`AuthService` créée à l'étape 06: **aucun controller ne change**.

---

## Démarrer

```bash
docker compose up -d db-example mailpit
pip install -r requirements.txt      # + PyJWT
./sqlAlchemy.sh -u
python main.py
```

Connectez-vous, puis regardez les cookies: plus de `session` porteuse d'identité,
un `access_token` à la place. Collez sa valeur dans <https://jwt.io> — vous lisez
son contenu (ce n'est pas chiffré), mais vous ne pouvez pas le modifier.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/services/auth_service_jwt.py` | **nouveau** — l'implémentation JWT |
| `app/services/auth_service_impl.py` | garde son code, **perd son `@injectable`** |
| `requirements.txt` | `PyJWT` |
| `.env` | `JWT_ACCESS_MINUTES` |

**Et c'est tout.** Pas une ligne modifiée dans les controllers, les templates ou
`@auth_required`.

### 1. Le basculement tient en un décorateur

```python
# auth_service_impl.py  (session)
# @injectable(base=AuthService, scope=Scope.SCOPED)      <- retiré
class AuthServiceImpl(AuthService): ...

# auth_service_jwt.py   (JWT)
@injectable(base=AuthService, scope=Scope.SCOPED)        <- posé ici
class AuthServiceJwt(AuthService): ...
```

Les vues annotent `auth_service: AuthService`; l'injecteur livre ce que le
décorateur désigne. C'est exactement ce que l'étape 06 annonçait sans pouvoir le
démontrer.

⚠️ Deux classes décorées avec `base=AuthService` en même temps: la **dernière
importée gagne**, silencieusement (ordre alphabétique des fichiers). Une seule à
la fois.

### 2. Où mettre le token: cookie ou en-tête ?

| | En-tête `Authorization: Bearer` | Cookie httpOnly |
|---|---|---|
| Pour | une API, un front séparé | un site rendu côté serveur |
| Stockage client | à la charge du JS (`localStorage` = lisible par tout XSS) | le navigateur, invisible au JS |
| Envoi | explicite | **automatique** |
| CSRF | impossible (pas d'envoi automatique) | **possible: protection obligatoire** |

Ce projet étant en MVC, le token va dans un **cookie httpOnly**. Donc:

> **Le JWT ne dispense pas du CSRF.** L'idée que « JWT = plus besoin de CSRF » est
> vraie uniquement pour un token envoyé à la main dans un en-tête. Dans un cookie,
> le navigateur l'envoie tout seul, et `CSRFProtect` reste indispensable. C'est
> vérifié par un test de cette étape.

Les deux modes sont lus (`read_token`): le cookie pour les pages, l'en-tête pour
qu'un client d'API puisse utiliser les mêmes routes.

### 3. `algorithms=` n'est pas optionnel

```python
jwt.decode(token, app.config['SECRET_KEY'], algorithms=[self.ALGORITHM])
```

C'est une **liste blanche**. Sans elle, un attaquant présente un token signé avec
l'algorithme `none` et devient administrateur. C'est la faille la plus connue de
l'écosystème JWT — testée dans cette étape (`token alg=none refusé`).

### 4. Le compromis: des données périmées

Les rôles voyagent dans les claims, donc `@auth_required` autorise **sans une
seule requête SQL** (vérifié: zéro requête pour identifier l'utilisateur). Le
prix: un rôle retiré reste valable jusqu'à l'expiration du token.

Ce projet en donne un exemple concret et gênant: un compte qui confirme son
adresse email garde un token disant `email_verified: false` — le bandeau reste
affiché et le checkout reste refusé. Le lien de confirmation est souvent ouvert
dans un **autre navigateur**, donc on ne peut pas compter sur cette requête pour
rafraîchir le cookie.

La règle retenue, dans `get_current_user()`:

> **un claim qui autorise doit être soit très court, soit revérifié.**

On relit donc la base, mais **uniquement quand le claim est défavorable** — et on
réémet le token à jour. Coût: une requête pour les seuls comptes non confirmés, et
le chemin rapide (zéro SQL) pour tous les autres.

### 5. Ce que le JWT rend inutile, et ce qu'il perd

| | Session (étapes 06-13) | JWT (ici) |
|---|---|---|
| Où vit l'identité | cookie signé, lu à chaque requête | dans le token |
| Requête SQL pour autoriser | 1 (rechargement du user) | 0 |
| Rotation de session | nécessaire (étape 12) | **sans objet** |
| Révocation immédiate | oui (`session.clear()`) | **impossible** |
| Rôles à jour | immédiatement | à l'expiration du token |

La ligne qui fait mal est « révocation impossible »: un token volé reste valable
jusqu'à `exp`. Deux réponses: un `exp` court (mais alors on se reconnecte toutes
les 15 minutes…) ou un **refresh token**. C'est l'étape suivante.

### 6. Le fichier session est conservé

`auth_service_impl.py` reste dans le projet, décorateur commenté. C'est
volontaire: comparer les deux implémentations côte à côte est plus parlant qu'un
`git log`. Pour revenir à la session, on déplace le décorateur — et rien d'autre.

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/19-jwt.md`](docs/19-jwt.md) — et [`docs/09-authentification.md`](docs/09-authentification.md)
pour la version session, avec laquelle comparer.

---

## Étape suivante

[`15-jwt-refresh-token`](../15-jwt-refresh-token/) — access token court + refresh
token révocable, avec rotation et détection de rejeu.
