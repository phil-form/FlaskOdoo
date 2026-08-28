# Étape 16 — Conversion en API

L'application rend du HTML. On lui ajoute une **API JSON**, sous `/api`, pour
les clients qui ne sont pas des navigateurs: application mobile, script,
service tiers, front-end mono-page.

Le résultat vaut d'être annoncé tout de suite: **aucun service, aucun modèle,
aucun mapper n'a été modifié.** Un fichier de controller, trois fichiers de
framework. Si l'ajout d'une API demande de toucher aux services, c'est que la
logique métier avait fui dans les controllers — l'API est un excellent
révélateur d'architecture.

**Pourquoi ici, juste après les deux étapes de tokens?** Parce que l'API est la
raison d'être de ce qui vient d'être écrit. Les étapes 14 et 15 ont remplacé la
session par une paire de tokens en disant, à chaque page, « et ça marchera aussi
pour un client qui n'est pas un navigateur ». Cette étape est l'endroit où on le
vérifie, pendant que le sujet est encore chaud: `AuthServiceJwt` lit déjà le
token dans l'en-tête `Authorization` autant que dans un cookie, et l'API se
contente d'exiger le premier.

C'est aussi la dernière étape avant que le parcours ne reparte vers l'intérieur
du code (abstractions, DTO, i18n, N+1). Chacune de ces étapes suivantes touchera
l'API à son tour, en une ligne ou deux — et c'est la démonstration la plus
courte qu'on puisse faire d'un couplage sain: on modifie le domaine, les deux
façades suivent.

---

## Démarrer

```bash
docker compose up -d db-example mailpit
pip install -r requirements.txt
./sqlAlchemy.sh -u          # aucune migration nouvelle
python main.py
```

```bash
# catalogue: route publique
curl -s localhost:8080/api/items | jq

# connexion
TOKEN=$(curl -s -X POST localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}' | jq -r .data.access_token)

curl -s localhost:8080/api/me -H "Authorization: Bearer $TOKEN" | jq
curl -s localhost:8080/api/basket -H "Authorization: Bearer $TOKEN" | jq
```

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/controllers/api_controller.py` | **nouveau** — le blueprint et toutes les routes |
| `app/framework/api.py` | **nouveau** — enveloppes JSON, pagination, `to_formdata` |
| `app/framework/decorators/api_auth_required.py` | **nouveau** — 401/403 au lieu d'une redirection |
| `app/framework/token_issuer.py` | **nouveau** — l'interface « émettre un token » |
| `app/services/auth_service_jwt.py` | second `@injectable`, implémente `TokenIssuer` |
| `app/framework/rate_limiter.py` | 429 en JSON sous `/api` |

### 1. Ce qui a rendu la conversion facile

Trois décisions prises bien avant cette étape:

- les **services** ne connaissent ni `request` ni `render_template` (étape 04);
  ils sont appelables depuis n'importe quelle façade;
- `AbstractDTO.get_json_parsable()` existe depuis l'étape 04 et **n'avait
  jamais servi**. C'était pour aujourd'hui;
- l'**authentification par token** (étapes 14–15) fonctionne déjà sans cookie,
  donc sans navigateur.

### 2. Le CSRF, et la seule condition qui permet de s'en passer

```python
csrf.exempt(api)
```

Cette ligne est dangereuse — sauf si une autre est respectée. Le jeton CSRF
protège les requêtes authentifiées **par cookie**: le navigateur l'envoie tout
seul, y compris pour une requête déclenchée par un site tiers.

`@api_auth_required` exige `Authorization: Bearer` et **refuse le cookie**. Or
aucun site tiers ne peut ajouter un en-tête à une requête qu'il déclenche. Le
CSRF n'a donc plus rien à protéger.

> **API sans CSRF ⇒ API qui n'accepte pas les cookies d'authentification.**

Exempter le blueprint tout en acceptant le cookie ouvrirait chaque route
d'écriture de l'application à n'importe quel site du web. C'est une des erreurs
les plus coûteuses de cette liste, et elle est facile à commettre puisque
`AuthServiceJwt` sait lire les deux.

### 3. 401 ou 403, et pourquoi ça compte

| Code | Sens | Ce que le client doit faire |
|---|---|---|
| `401` | « je ne sais pas qui vous êtes » | s'authentifier, ou rafraîchir son token |
| `403` | « je sais, et non » | renoncer (réessayer est inutile) |
| `422` | données invalides | corriger le corps de la requête |
| `409` | conflit métier (stock, panier vide) | changer l'intention |
| `204` | fait, rien à dire | ne rien lire |

Un 403 à la place d'un 401 envoie le client dans une boucle de reconnexion; un
401 à la place d'un 403 lui fait croire que son token est cassé.

### 4. Ne jamais répondre du HTML

Sans gestionnaire dédié, `/api/inexistant` renvoie la page d'erreur de Flask.
Le client reçoit `<!DOCTYPE html>`, son parseur JSON échoue, et son message
parle de syntaxe au lieu de parler de route introuvable.

```python
@app.errorhandler(404)
def erreurs_json(erreur):
    if not request.path.startswith('/api'):
        return erreur
    ...
```

Le gestionnaire est **global** avec un test sur le chemin, et non
`@api.errorhandler`: un 404 se produit avant que Flask ait associé la requête à
un blueprint — il ne sait pas que l'URL visée était celle de l'API. Le préfixe
d'URL est la seule information disponible à ce moment-là.

Même raisonnement pour le `429` du limiteur de débit.

### 5. Réutiliser les formulaires, et le piège du zéro

Les validators de l'étape 04 valent autant pour un client d'API que pour un
navigateur. On alimente donc les mêmes `FlaskForm` avec le corps JSON — mais il
y a deux marches:

```python
classe(formdata=to_formdata(json_body()), meta={'csrf': False})
```

- `data=` pose une valeur par défaut, `formdata=` **simule une saisie**.
  `InputRequired` ne regarde que `field.raw_data`, rempli uniquement par
  `formdata`;
- il faut en plus convertir en **chaînes**. `InputRequired` teste littéralement
  `if field.raw_data and field.raw_data[0]`: avec l'entier `0` de JSON, c'est
  faux. Un navigateur envoie `"0"`, qui est vrai.

Sans ça, l'API refuse toute création d'article avec un stock à zéro, en
accusant un champ pourtant fourni. C'est le **troisième avatar du même piège**
dans ce projet, après `DataRequired` vs `InputRequired` à l'étape 04: zéro
n'est pas l'absence de valeur.

### 6. Deux interfaces plutôt qu'une

```python
@injectable(base=AuthService, scope=Scope.SCOPED)
@injectable(base=TokenIssuer, scope=Scope.SCOPED)
class AuthServiceJwt(AuthService, TokenIssuer):
```

L'API a besoin de **fabriquer** un token, ce qu'`AuthService` ne sait pas faire
— et ne doit pas savoir faire: `AuthServiceImpl` (session) n'aurait aucun sens à
implémenter `encode()`. Deux interfaces, chacune signée par qui sait la tenir.

Les deux décorateurs empilés fonctionnent parce que `@injectable` retourne la
classe **inchangée**: chacun ajoute une ligne au registre. Un controller MVC
demande `AuthService`, un controller d'API demande `TokenIssuer`, tous deux
reçoivent la même instance (scope `SCOPED`).

### 7. Deux transports pour le refresh token

`/api/auth/refresh` prend le refresh token **dans le corps JSON**, alors que le
parcours navigateur le reçoit dans un cookie confiné à `/auth/refresh`
(étape 15). Le service est le même, `RefreshTokenService.rotate()`: seul le
transport change.

```
navigateur   cookie httpOnly, SameSite=Strict, Path=/auth/refresh
client d'API corps JSON, stocké par le client lui-même
```

Aucun des deux n'est parfait, et il faut le dire dans cet ordre:

- le **cookie** n'est pas lisible par du JavaScript, mais il part tout seul —
  d'où `SameSite=Strict`, le `Path` restreint, et le CSRF sur les pages HTML;
- le **corps JSON** oblige le client à ranger le token quelque part. Dans une
  application mono-page, ce « quelque part » est `localStorage`, lisible par
  n'importe quel XSS. C'est pour ça qu'une application mono-page servie par
  notre propre domaine a intérêt à utiliser le parcours cookie, et à laisser
  le corps JSON aux clients qui n'ont pas de navigateur.

La déconnexion suit la même logique: l'API révoque le refresh token qu'on lui
présente, la page HTML révoque la famille désignée par le claim `fam` — parce
qu'elle, justement, ne voit pas le token.

### 8. Ce que l'API révèle sur le code existant

`api_basket_checkout` revérifie `email_verified` — comme le controller HTML.
**La règle est donc écrite deux fois.** Ce n'est pas une fatalité de l'API:
c'est le signe qu'elle aurait dû vivre dans `BasketService.checkout()`. Une
règle métier dupliquée dans deux façades finit toujours par diverger.

C'est l'exercice 3, et c'est le vrai enseignement de l'étape.

### 9. Ce qui n'est pas fait

- **pas de versionnement** (`/api/v1/`). Une API publique a des clients qu'on
  ne peut pas déployer: c'est une faute dans un vrai produit, un exercice ici;
- **pagination en Python**, après avoir tout chargé. Honnête sur six articles,
  faux dès que la table est grosse. L'étape 20 donnera l'outil pour le
  constater; la vraie pagination se fait en SQL;
- **pas de documentation** OpenAPI, pas de CORS, pas de format d'erreur
  normalisé (RFC 9457 `application/problem+json`);
- l'API expose une partie du domaine seulement (ni inscription, ni gestion des
  utilisateurs au-delà de la liste).

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/21-api-json.md`](docs/21-api-json.md)

---

## Étape suivante

[`../17-abstractions-du-framework/`](../17-abstractions-du-framework/) — quatre
fichiers du framework maison vivent encore dans l'application. On les range, et
l'API en profite dès la première ligne: son import d'`AuthService` change de
dossier.
