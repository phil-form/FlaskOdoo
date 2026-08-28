# Exercices — Étape 16

## 1. Casser l'exemption CSRF

**Objectif** — vérifier soi-même la condition qui rend `csrf.exempt` acceptable.

1. Dans `api_auth_required`, retirez la vérification de l'en-tête
   `Authorization` (laissez `auth_service.get_current_user()` faire son
   travail). L'API accepte désormais le cookie.
2. Connectez-vous dans le navigateur (pages HTML), puis ouvrez un fichier HTML
   local contenant:
   ```html
   <form method="post" action="http://localhost:8080/api/items">
     <input name="name" value="pirate"><input name="description" value="x">
     <input name="stock" value="1"><button>go</button>
   </form>
   ```
3. Cliquez. Regardez la base. Que s'est-il passé ?
4. Remettez la vérification. Refaites l'essai.
5. Écrivez la règle en une phrase, à afficher au-dessus de tout `csrf.exempt`.

<details>
<summary>Coup de pouce</summary>

Un formulaire HTML peut poster vers n'importe quel domaine, et le navigateur
joint les cookies. Il ne peut PAS ajouter d'en-tête `Authorization`. C'est toute
la différence, et c'est pour ça que la règle est « pas de cookie », pas « pas de
CSRF ».
</details>

**Critère de réussite** — vous avez créé un article depuis un autre « site »,
puis rendu l'attaque impossible.

## 2. Le zéro qui disparaît

**Objectif** — comprendre un bug de validation plutôt que le contourner.

1. Remplacez `to_formdata(json_body())` par `data=json_body()`.
2. `POST /api/items` avec `{"name":"x","description":"y","stock":0}`. Que dit
   l'erreur ? Le champ était-il fourni ?
3. Passez à `MultiDict(json_body())` (sans conversion en chaînes). Même essai.
   Toujours en échec ? Pourquoi ?
4. Lisez le code source d'`InputRequired` dans WTForms. Écrivez la ligne exacte
   qui cause le problème.
5. Retrouvez le même piège à l'étape 04 (`DataRequired` sur `stock`). Formulez
   la règle générale.

**Critère de réussite** — vous savez expliquer les trois comportements
(`data`, `MultiDict` d'entiers, `MultiDict` de chaînes) sans relire le README.

## 3. Une règle métier, un seul endroit

**Objectif** — supprimer la duplication que l'API vient de révéler.

`email_verified` est vérifié dans `basket_controller.checkout` **et** dans
`api_basket_checkout`. Deux façades, deux copies de la même règle.

1. Déplacez la règle dans `BasketService.checkout()`.
2. Problème: le service retourne `None` pour « panier vide », « stock
   insuffisant » **et** maintenant « email non confirmé ». Le controller ne
   peut plus produire le bon message ni le bon code HTTP. Comment un service
   communique-t-il *pourquoi* il a refusé ?
3. Comparez trois solutions: un tuple `(resultat, raison)`, une exception
   métier, un objet `Resultat`. Implémentez-en une.
4. Vérifiez que les DEUX façades affichent le bon message et le bon code.
5. Question de fond: quelles autres règles du projet sont dans les controllers
   alors qu'elles devraient être dans les services ? Faites la liste.

<details>
<summary>Coup de pouce</summary>

C'est le vrai enseignement de l'étape. Une API n'ajoute pas de duplication:
elle **révèle** celle qui existait déjà, parce qu'une règle écrite dans un
controller n'a jamais qu'un seul appelant — jusqu'au jour où il y en a deux.
</details>

**Critère de réussite** — la règle est écrite une fois, les deux façades sont
correctes, et vous avez la liste des autres cas.

## 4. Versionner

**Objectif** — pouvoir changer un contrat sans casser ses clients.

1. Passez le blueprint sous `/api/v1`.
2. Créez `/api/v2/items` où un article expose `label` au lieu de `name`.
3. Combien de code avez-vous dupliqué ? Comment l'éviter ? (Indice: la version
   ne concerne que la **représentation** — relisez l'étape 18.)
4. Comment savoir quand `/v1` peut être supprimé ? Quelle instrumentation
   faut-il pour répondre à cette question avec des chiffres ?
5. Une alternative existe: la version dans un en-tête (`Accept:
   application/vnd.monapi.v2+json`). Avantages, inconvénients ?

**Critère de réussite** — les deux versions coexistent sans duplication de
logique, et vous savez dire ce qui vous manque pour retirer la v1.

## 5. Paginer pour de vrai

**Objectif** — remplacer une simplification assumée.

`paginate()` découpe une liste **déjà entièrement chargée**.

1. Insérez 50 000 articles. Mesurez `/api/items?page=1&per_page=20`.
2. Faites paginer en SQL (`.paginate()` de Flask-SQLAlchemy, ou
   `limit`/`offset`). Remesurez.
3. Mesurez maintenant `?page=2000`. Pourquoi `OFFSET` reste-t-il lent ?
4. Implémentez une pagination **par curseur** (`?after=<item_id>`). Que
   perd-on ? (Indice: peut-on encore sauter à la page 47 ?)
5. Ajoutez `Link` (RFC 8288) dans les en-têtes de réponse.

**Critère de réussite** — trois mesures, et un avis sur offset vs curseur.

## 6. Documenter

**Objectif** — une API non documentée n'a pas de clients.

1. Écrivez un fichier OpenAPI décrivant au moins `/auth/login`, `/items` et
   `/basket`.
2. Servez-le sur `/api/openapi.json` et branchez une interface (Swagger UI,
   Redoc). Attention à la CSP de l'étape 12: qu'avez-vous dû ajuster ?
3. Question de maintenance: un fichier écrit à la main diverge du code en trois
   mois. Quelles approches évitent ça ? (`apispec`, `flask-smorest`,
   `pydantic` + génération.)
4. Le format d'erreur du projet est maison. Comparez-le à la RFC 9457
   (`application/problem+json`). Faut-il migrer ?

**Critère de réussite** — la documentation s'affiche, et vous avez tranché la
question 3.

## 7. Un client, pour de vrai

**Objectif** — éprouver l'API depuis l'extérieur.

1. Écrivez un script Python (`requests`) qui: se connecte, liste le catalogue,
   ajoute un article au panier, valide la commande.
2. Faites-le survivre à l'expiration de l'access token (15 minutes): il doit
   appeler `/auth/refresh` sur un 401 et rejouer la requête.
3. Attention au piège: que se passe-t-il si **deux** requêtes reçoivent un 401
   en même temps et rafraîchissent toutes les deux ? (Relisez la détection de
   rejeu de l'étape 15.)
4. Révoquez proprement le refresh token en fin de script (`/auth/logout`), et
   vérifiez en base que la ligne est bien marquée consommée.
5. Ajoutez le respect de `Retry-After` sur un 429.

**Critère de réussite** — le script tourne vingt minutes sans intervention, et
ne déclenche jamais une révocation de famille.

## 8. CORS

**Objectif** — le mécanisme que tout le monde désactive sans le comprendre.

1. Servez une page HTML depuis un autre port (`python -m http.server 9000`) et
   faites-lui appeler `/api/items` en `fetch()`. Que dit la console ?
2. Ajoutez les en-têtes CORS à la main (pas de bibliothèque) pour autoriser
   cette origine.
3. Faites une requête `DELETE` avec un en-tête `Authorization`. Une requête
   supplémentaire apparaît: laquelle, et pourquoi ?
4. Pourquoi `Access-Control-Allow-Origin: *` est-il refusé dès qu'on veut
   `Allow-Credentials: true` ?
5. Le CORS protège-t-il votre serveur ? (Réponse courte: non. Expliquez ce
   qu'il protège réellement.)

**Critère de réussite** — la page tierce appelle l'API, et vous savez répondre
à la question 5 en deux phrases.
