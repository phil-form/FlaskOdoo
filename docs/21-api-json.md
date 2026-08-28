# 21 — API JSON

Fichiers: `app/controllers/api_controller.py`, `app/framework/api.py`,
`app/framework/decorators/api_auth_required.py`,
`app/framework/token_issuer.py`

Une API n'est pas une réécriture de l'application: c'est une **deuxième façade**
sur le même métier. Si l'ajouter demande de modifier les services, c'est que la
logique avait fui dans les controllers.

Dans ce projet, la conversion n'a touché **aucun service, aucun modèle, aucun
mapper**. Trois décisions antérieures l'expliquent:

| Décision | Étape | Ce qu'elle rend possible |
|---|---|---|
| services sans `request` ni `render_template` | 04 | le métier est appelable depuis n'importe où |
| `AbstractDTO.get_json_parsable()` | 04 | la sérialisation existe déjà |
| authentification par token | 14–15 | ça marche sans navigateur |

## CSRF: la règle

```python
csrf.exempt(api)
```

Acceptable **à une condition**, appliquée par `@api_auth_required`: l'API
n'accepte pas les cookies d'authentification, seulement
`Authorization: Bearer`.

Un cookie part tout seul, y compris sur une requête déclenchée par un site
tiers — c'est la définition du CSRF. Un en-tête doit être ajouté explicitement
par le client, et aucun site tiers ne peut le faire.

> API sans CSRF ⇒ API qui refuse les cookies d'authentification.

Exempter le blueprint en acceptant le cookie ouvre chaque route d'écriture au
web entier. L'erreur est facile: la même implémentation JWT sait lire les deux
transports.

## Les codes de statut

| Code | Sens | Réaction attendue du client |
|---|---|---|
| 200 / 201 / 204 | succès (avec / créé / sans contenu) | — |
| 401 | identité inconnue | s'authentifier ou rafraîchir |
| 403 | identité connue, droits insuffisants | renoncer |
| 404 | ressource inexistante | — |
| 409 | conflit métier (stock, panier vide) | changer l'intention |
| 422 | corps invalide | corriger les champs |
| 429 | trop de requêtes | attendre `Retry-After` |

401 et 403 ne sont pas interchangeables: confondre les deux envoie un client
dans une boucle de reconnexion, ou lui fait croire que son token est cassé.
Un `201` s'accompagne d'un en-tête `Location`; un `204` n'a pas de corps —
`{"success": true}` est du bruit que le code de statut dit déjà mieux.

## Jamais de HTML

Un client d'API qui reçoit `<!DOCTYPE html>` signale une erreur de *parsing*,
pas une erreur d'authentification ou de route. Il faut donc intercepter 404,
405, 500 et 429.

Le gestionnaire est **global**, avec un test sur `request.path`, et non
`@api.errorhandler`: un 404 survient avant que Flask ait pu associer la requête
à un blueprint. Le préfixe d'URL est la seule information disponible.

## Réutiliser les formulaires

Les validators écrits pour le HTML valent pour le JSON. Deux marches à
connaître:

- `data=` pose une valeur par défaut, `formdata=` **simule une saisie**. Les
  validators de présence ne regardent que `raw_data`, rempli par `formdata`;
- les valeurs doivent être des **chaînes**: `InputRequired` teste
  `if field.raw_data[0]`, et l'entier `0` est faux. Un navigateur envoie
  `"0"`.

Sans ça, l'API refuse toute création avec une valeur numérique nulle, en
accusant un champ pourtant fourni. C'est le même piège qu'au chapitre 06
(`DataRequired` vs `InputRequired`): **zéro n'est pas l'absence de valeur**.

## Deux interfaces plutôt qu'une

`AuthService` répond « qui est connecté? » — utile aux deux façades, et
implémentable par une session comme par un token. `TokenIssuer` répond
« fabrique-moi un token » — utile à l'API seule, et sans aucun sens pour une
implémentation à base de session.

Les fusionner obligerait `AuthServiceImpl` à signer des méthodes qu'elle ne sait
pas tenir: c'est la définition d'une interface trop grosse.

L'injecteur maison accepte les deux enregistrements sur la même classe, parce
que `@injectable` retourne la classe inchangée.

## Deux transports pour le refresh token

`/api/auth/refresh` reçoit le refresh token **dans le corps JSON**; le parcours
navigateur le reçoit dans un cookie confiné à `/auth/refresh` (chapitre 20). Le
service est le même, `RefreshTokenService.rotate()` — seul le transport change,
et c'est exactement le genre de distinction qui doit rester hors des services.

| | Navigateur | Client d'API |
|---|---|---|
| Refresh token | cookie httpOnly, `SameSite=Strict`, `Path=/auth/refresh` | corps JSON |
| Rangé par | le navigateur, invisible au JS | le client lui-même |
| Renouvellement | redirection `/auth/refresh?next=…` | appel explicite sur 401 |
| Déconnexion | révoque la famille du claim `fam` | révoque le token présenté |

Aucun des deux n'est parfait: le cookie part tout seul (d'où `SameSite`, le
`Path` et le CSRF), le corps JSON oblige le client à ranger le token quelque
part — dans une application mono-page, ce « quelque part » est `localStorage`,
lisible par n'importe quel XSS.

D'où la règle pratique: une application mono-page servie par **notre** domaine a
intérêt au parcours cookie; le corps JSON est pour les clients qui n'ont pas de
navigateur.

## Ce que l'API révèle

La vérification `email_verified` existe dans le controller HTML **et** dans le
controller d'API. La duplication n'est pas causée par l'API: elle est
**révélée** par elle. Une règle métier écrite dans un controller n'a qu'un seul
appelant — jusqu'au jour où il y en a deux.

C'est le meilleur usage d'une API pour un projet existant: un test
d'architecture qui ne ment pas.

## Ce qu'il manquerait en production

- **versionner l'URL** (`/api/v1/`): les clients ne se redéploient pas;
- **paginer en SQL**, et de préférence par curseur au-delà de quelques pages;
- **documenter** (OpenAPI), et de préférence à partir du code;
- un **format d'erreur normalisé** (RFC 9457, `application/problem+json`)
  plutôt qu'une enveloppe maison;
- **CORS**, si des navigateurs d'autres origines doivent appeler l'API.
