# 10 — Controllers & routes

Fichiers: `app/controllers/`

## Ce que fait (et ne fait pas) un controller

Il fait quatre choses:

1. recevoir la requête HTTP,
2. valider l'entrée via un formulaire,
3. appeler un service,
4. choisir la réponse: un template ou une redirection.

Il ne fait **jamais**: de requête SQL, de calcul métier, de mise en forme
compliquée. Un controller qui dépasse quinze lignes cache probablement de la
logique qui appartient à un service.

## Déclarer une route

```python
@app.get('/items')                                  # raccourci de
@app.route('/items', methods=['GET'])               # ceci
@app.post('/basket/add')                            # idem pour POST
@app.route('/items/add', methods=['GET', 'POST'])   # les deux sur la même vue
```

Le **nom de la fonction devient le nom du endpoint**, celui qu'on utilise dans
`url_for('item_list')`. Deux vues ne peuvent pas porter le même nom.

### Les paramètres d'URL

```python
@app.get('/items/<int:item_id>')
def item_details(item_id: int, ...):
```

Le convertisseur `<int:...>` garantit que `item_id` est un entier: `/items/abc`
donne un 404 avant même d'entrer dans la vue. Autres convertisseurs:
`<string:x>` (par défaut, sans `/`), `<path:x>` (accepte les `/`),
`<uuid:x>`, `<float:x>`.

### url_for, jamais d'URL en dur

```jinja
<a href="{{ url_for('item_details', item_id=item.item_id) }}">Détails</a>
```

Les arguments qui ne correspondent pas à un paramètre de route deviennent des
paramètres de requête: `url_for('login', next='/basket')` → `/login?next=/basket`.
Renommer une URL ne casse alors aucun lien.

## POST / Redirect / GET

Le motif structurant de tout le projet:

```python
@app.route('/items/add', methods=['GET', 'POST'])
@auth_required(level="ADMIN")
@inject
def item_add(item_service: ItemService):
    form = ItemForm()

    if form.validate_on_submit():                 # POST valide
        item = item_service.insert(form)
        if item is None:
            flash("Impossible de créer l'article (nom déjà pris?).", "danger")
        else:
            flash(f"Article « {item.name} » créé.", "success")
            return redirect(url_for('item_list'))     # ← REDIRECTION

    return render_template('items/add_or_update.html', form=form, item=None)
```

Pourquoi rediriger après un POST réussi plutôt que rendre la page directement?

- **F5.** Si la réponse du POST est une page, un rafraîchissement renvoie le
  formulaire: double article, double commande, et un avertissement du navigateur.
- **URL cohérente.** Après création, la barre d'adresse doit afficher
  `/items`, pas `/items/add`.
- **Bouton retour** utilisable normalement.

Et en cas d'échec: **pas** de redirection. On rend le même template, avec le
formulaire — donc les saisies et les messages d'erreur sont conservés.

Le code de redirection par défaut est 302. `redirect(url, code=303)` est plus
correct après un POST, mais tous les navigateurs traitent le 302 comme un 303
depuis longtemps.

## flash(): parler à l'utilisateur après une redirection

```python
flash("Panier mis à jour.", "success")
```

Le message est déposé en session, et consommé (une seule fois) au rendu suivant
par le layout:

```jinja
{% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}
        <div class="alert alert-{{ category }}">{{ message }}</div>
    {% endfor %}
{% endwith %}
```

Les catégories utilisées correspondent aux classes Bootstrap: `success`, `danger`,
`warning`, `info`. C'est le seul mécanisme qui survit à une redirection — une
variable de template, non.

## Les cinq routes d'une ressource

Pour `Item`, en MVC:

| Méthode | URL | Vue | Rôle |
|---|---|---|---|
| GET | `/items` | `item_list` | liste |
| GET | `/items/<id>` | `item_details` | détail |
| GET/POST | `/items/add` | `item_add` | formulaire + création |
| GET/POST | `/items/<id>/edit` | `item_update` | formulaire + modification |
| POST | `/items/<id>/delete` | `item_delete` | suppression |

Une API REST utiliserait `PUT /items/<id>` et `DELETE /items/<id>`. Un formulaire
HTML ne sait envoyer que GET et POST: en MVC, toute action qui modifie l'état est
donc en POST.

**Et jamais en GET.** Un `<a href="/items/1/delete">` serait déclenché par un
préchargement de lien, un aperçu dans une messagerie, ou un robot d'indexation.
D'où la macro `delete_button` qui génère un mini-formulaire POST déguisé en
bouton.

## Gérer l'absence

```python
item = item_service.find_one(item_id)

if item is None:
    flash("Article introuvable.", "warning")
    return redirect(url_for('item_list'))
```

`abort(404)` serait plus correct au sens HTTP; en MVC on préfère souvent un
message + redirection, plus agréable. Choisissez, mais soyez cohérent: ici, tout
le projet fait flash + redirect.

## Rester dans la même page: request.referrer

```python
return redirect(request.referrer or url_for('item_list'))
```

`basket_add_item` est appelée depuis le catalogue **et** depuis le panier. Le
`Referer` renvoie l'utilisateur d'où il venait. Il peut être absent (client qui ne
l'envoie pas), d'où le `or` — ne jamais supposer sa présence.

## Le controller de test

`test_controller.py` est conservé tel quel: il montre le minimum absolu (pas de
service, pas de base) et une vue qui renvoie une simple chaîne de caractères.
Flask en fait une réponse HTTP 200 en `text/html`.

```python
@app.get('/autre')
def test2():
    return "<h1>Mon autre page</h1>"
```

## Un controller par ressource

Tous les controllers font `from app import app` et décorent `@app.route`. Le
découpage se fait donc par **fichier**, un par ressource:

```
app/controllers/
├── home_controller.py      /
├── item_controller.py      /items...
├── user_controller.py      /users, /login, /register, /profile
└── basket_controller.py    /basket, /baskets
```

Chaque fichier regroupe les routes d'un même domaine et est découvert
automatiquement (voir `app/controllers/__init__.py`). Ajouter une ressource =
ajouter un fichier.

Une convention à tenir, puisque les endpoints vivent tous dans le même espace de
noms: **préfixer le nom des vues par la ressource** — `item_list`,
`item_details`, `item_add`, `basket_add_item`. Deux vues ne peuvent pas porter le
même nom, et `url_for('item_list')` reste lisible sans avoir à chercher dans quel
fichier la route est déclarée.
