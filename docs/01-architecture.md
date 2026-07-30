# 01 — Architecture

## MVC, en version serveur

MVC découpe l'application en trois responsabilités:

- **Modèle** — les données et les règles qui les concernent
  (`app/models/`, `app/services/`)
- **Vue** — la présentation (`app/templates/`)
- **Controller** — la glue entre les deux (`app/controllers/`)

Ici les vues sont des pages HTML complètes générées par le serveur. Le
navigateur envoie un formulaire, le serveur répond par une page ou une
redirection. Pas de JavaScript indispensable, pas de JSON.

L'autre approche, celle du dépôt
[pythonORM](https://github.com/phil-form/pythonORM), est l'API: le serveur
renvoie du JSON (`jsonify`) et c'est le JavaScript du navigateur qui construit
les pages. Les différences concrètes:

| | MVC serveur (ce projet) | API JSON |
|---|---|---|
| Réponse d'une vue | `render_template(...)` / `redirect(...)` | `jsonify(...)` |
| Après un POST réussi | redirection (POST/Redirect/GET) | code HTTP + corps JSON |
| Formulaires | `FlaskForm()` lit `request.form` | `Form.from_json(request.json)` |
| Erreurs de validation | réaffichage du formulaire avec les messages | `jsonify(form.errors)` |
| Authentification | session (cookie signé) | token JWT dans un en-tête |
| Accès refusé | `redirect` vers `/login` | `401` / `403` |

Ce qui **ne change pas**: modèles, DTO, mappers, services. C'est tout l'intérêt
du découpage: la couche métier ne sait pas si elle sert du HTML ou du JSON.

## Les couches, de bas en haut

```
                    ┌─────────────────────────────┐
   navigateur  ───► │ controllers/                │  HTTP: route, form, redirect
                    ├─────────────────────────────┤
                    │ services/                   │  logique métier + transactions
                    ├──────────────┬──────────────┤
                    │ mappers/     │ forms/       │  traduction / validation
                    ├──────────────┼──────────────┤
                    │ dtos/        │ models/      │  transport / persistance
                    └──────────────┴──────────────┘
                                   │
                              PostgreSQL
```

Règles que le projet ne viole jamais:

1. **Un controller ne fait pas de requête SQL.** Aucun `Model.query` ni
   `db.session` dans `app/controllers/`. Vérifiable d'un `grep`.
2. **Un service ne connaît pas HTTP.** Pas de `request`, pas de `redirect`, pas
   de `render_template`. Le user courant lui est *passé en paramètre*
   (`basket_service.add_item(user_id, form)`), il ne va pas le chercher dans la
   session.
3. **Un modèle ne connaît que lui-même.** `Basket.add_item()` sait ajouter une
   ligne de panier, mais ne commit pas: c'est le service qui décide de la
   transaction.
4. **Un template ne reçoit que des DTO.** Ni entité, ni `db.session`.

## Le cycle de vie d'une requête

Exemple: `POST /basket/add` avec `item_id=3&quantity=2`.

```
1. Werkzeug/Flask   reçoit la requête, cherche la règle /basket/add
2. CSRFProtect      vérifie le jeton csrf_token du formulaire  -> 400 si absent
3. @auth_required   demande AuthService à l'injecteur, qui lit session['user_id'],
                    recharge le user en base -> redirection vers /login si anonyme
4. @inject          fournit basket_service et auth_service à la vue
5. la vue           BasketAddItemForm() lit request.form et valide
6. le service       retrouve l'article, retrouve LE PANIER DU USER (jamais un
                    basket_id posté), appelle basket.add_item(), commit
7. la vue           flash(...) + redirect(request.referrer)
8. le navigateur    suit la redirection: GET de la page précédente
9. le layout        get_flashed_messages() affiche le message une seule fois
```

Chaque étape est dans un fichier différent, et chacune est remplaçable sans
toucher les autres.

## Où va mon nouveau code ?

| Je veux… | Fichier |
|---|---|
| une nouvelle page | `app/controllers/xxx_controller.py` + `app/templates/xxx/` |
| une nouvelle table | `app/models/xxx.py` + une migration |
| une règle qui ne dépend que de l'entité (« un panier fermé n'accepte plus d'article ») | le modèle |
| une règle qui touche plusieurs entités ou la base | le service |
| valider une saisie utilisateur | le formulaire (`validators=[...]`) |
| changer ce qu'affiche une page | le template, ou le DTO s'il manque une donnée |
| des données de démo | `app/seed/xxx_seed.py` |
| un service injectable | `app/services/` + `@injectable` sur la classe |

## L'ordre d'initialisation

`app/__init__.py` se lit de haut en bas et l'ordre compte:

```python
load_dotenv()                  # 1. configuration
app = Flask("app")             # 2. l'objet application
db = SQLAlchemy(app)           #    puis les extensions
from app.models import *       # 3. les tables (sinon migrations vides)
from app.controllers import *  #    les routes (sinon 404 partout)
from app.services import *     # 4. les @injectable s'enregistrent...
injector = Injector(app)       #    ...avant que l'injecteur lise le registre
from app.seed import *         # 5. les Seedable s'enregistrent...
seed = Seed(app)               #    ...et la route /seed est ajoutée (debug only)
```

Quatre dossiers, **un seul mécanisme**: un `__all__` construit à partir du
contenu du dossier, et un `import *` qui déclenche les imports. Ce qui se passe à
l'import diffère (une table pour un modèle, une route pour un controller, une
entrée de registre pour un service ou un seeder), mais la découverte est
identique.

Les imports en bas de fichier violent PEP8 volontairement: les controllers font
`from app import app`, donc l'objet `app` doit déjà exister quand on les importe.
C'est l'import circulaire classique d'une application Flask construite autour
d'un objet `app` global. On l'accepte ici parce qu'il rend l'ordre
d'initialisation visible en un seul fichier, qui se lit de haut en bas.
