# FlaskOdoo — application MVC Flask (projet de formation)

> **Étape 09 de la formation** — c'est le projet terminé. Son code est
> identique à celui de l'étape 08; ce dossier ajoute la documentation
> complète ci-dessous. Voir [l'index des étapes](../README.md).

Une petite boutique en ligne écrite avec Flask, en **MVC serveur** (pages HTML
rendues par Jinja2, pas d'API JSON) et destinée à être lue autant qu'exécutée:
chaque fichier du projet est commenté pour expliquer *pourquoi* il est écrit
comme ça.

Fonctionnalités: catalogue d'articles, inscription/connexion, rôles
(USER/ADMIN), panier, validation de commande, administration des utilisateurs,
et un système de *seeding* pour repartir d'une base peuplée en une URL.

---

## Sommaire de la documentation

La documentation est découpée par couche, dans l'ordre où on la construit:

| # | Document | Sujet |
|---|---|---|
| 01 | [Architecture](docs/01-architecture.md) | les couches, le cycle d'une requête, le sens des dépendances |
| 02 | [Docker & configuration](docs/02-docker-et-configuration.md) | `docker-compose`, `.env`, `.env.local`, variables |
| 03 | [Modèles & relations](docs/03-modeles-et-relations.md) | SQLAlchemy, clés étrangères, one-to-many, many-to-many, cascades |
| 04 | [Migrations](docs/04-migrations.md) | Alembic, `sqlAlchemy.sh`, ajouter une colonne sans casser les données |
| 05 | [DTOs & mappers](docs/05-dtos-et-mappers.md) | pourquoi ne pas donner les entités aux templates |
| 06 | [Formulaires](docs/06-formulaires.md) | WTForms, validation, CSRF |
| 07 | [Services](docs/07-services.md) | logique métier, transactions, `commit`/`rollback` |
| 08 | [Injection de dépendances](docs/08-injection-de-dependances.md) | l'injecteur maison, les scopes, `@inject` |
| 09 | [Authentification & rôles](docs/09-authentification.md) | session, argon2, `@auth_required`, pièges de sécurité |
| 10 | [Controllers & routes](docs/10-controllers-et-routes.md) | POST/Redirect/GET, table des routes |
| 11 | [Templates Jinja2](docs/11-templates-jinja.md) | héritage, blocs, macros, includes, échappement |
| 12 | [Seeding](docs/12-seeding.md) | `Seedable`, auto-enregistrement, ordre, route de debug |
| 13 | [Exercices](docs/13-exercices.md) | ajouter une entité de bout en bout |

Un aide-mémoire condensé (les squelettes de code à recopier) se trouve dans
[readme.md](readme.md).

---

## Démarrage rapide

```bash
# 1. la base de données (PostgreSQL) + le serveur de mails de dev, dans Docker
docker compose up -d db-example mailpit

# 2. l'environnement Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. le schéma de la base
./sqlAlchemy.sh -u          # applique les migrations

# 4. le serveur
python main.py              # http://localhost:8080
```

Puis, en mode debug, visitez **<http://localhost:8080/seed>** pour insérer les
données de démonstration, et connectez-vous:

| Utilisateur | Mot de passe | Rôles |
|---|---|---|
| `admin` | `admin` | USER, ADMIN |
| `test` | `test` | USER |

> `/seed` n'existe QUE si `DEBUG=True`: une URL qui réinjecte des données de
> test ne doit jamais être joignable en production.

Deux interfaces web accompagnent le développement:

| Adresse | Quoi |
|---|---|
| <http://localhost:8080> | l'application |
| <http://localhost:8025> | **Mailpit**: tous les mails envoyés par l'app (« mot de passe oublié »). Rien ne part réellement. |

En debug, les règles de mot de passe sont volontairement souples (4 caractères);
en production elles passent à 12 caractères avec minuscule, majuscule et chiffre
— une ternaire dans `app/forms/user/user_register_form.py`.

---

## Structure du projet

```
FlaskOdoo/
├── main.py                     lanceur du serveur de dev
├── docker-compose.yml          l'app + PostgreSQL
├── sqlAlchemy.sh               raccourcis pour les migrations
├── requirements.txt            dépendances (chacune commentée)
├── .env / .env.local           configuration (le .local est git-ignoré)
├── migrations/                 migrations Alembic (générées + ajustées)
├── docs/                       la documentation détaillée
└── app/
    ├── __init__.py             création de l'app Flask, câblage, ordre des imports
    ├── models/                 les ENTITÉS (tables) + la logique propre à l'entité
    │   ├── base_entity.py      mixin: created_at, updated_at, active...
    │   ├── user.py  role.py  user_role.py
    │   ├── item.py  basket.py  basket_item.py
    │   └── LiItem.py           objet jetable des premiers exercices Jinja
    ├── dtos/                   objets de transfert (ce que voient les templates)
    ├── mappers/                Form -> Entity -> DTO
    ├── forms/                  formulaires WTForms (user/, item/, basket/)
    ├── services/               logique métier + accès base (la seule couche qui
    │                           parle à db.session), + mail_service et
    │                           password_reset_service
    ├── controllers/            les routes: HTTP -> service -> template
    ├── templates/              Jinja2: layout, macros, une page par vue,
    │                           emails/ pour les mails en texte brut
    ├── seed/                   les jeux de données de démonstration
    └── framework/              le "petit framework" maison
        ├── injector.py         conteneur d'injection de dépendances
        ├── decorators/         @injectable, @inject, @auth_required
        └── seed/               Seedable + Seed (route /seed en debug)
```

### Le sens des dépendances

```
controllers  ->  services  ->  mappers  ->  dtos
                    |             |     \
                    |             |      -> models
                    +-> forms ----+
```

Une flèche = "connaît". Un service connaît les modèles; un modèle ne connaît
aucun service. Un template ne reçoit que des DTO. Si vous vous retrouvez à
importer un controller depuis un service, c'est le signe qu'un bout de logique
est au mauvais endroit.

---

## Les trois mécanismes "magiques" du projet

Ils reviennent partout, autant les comprendre tout de suite.

### 1. Auto-découverte des modules

Les quatre dossiers découverts automatiquement — `models/`, `controllers/`,
`services/`, `seed/` — ont le même `__init__.py`, qui construit `__all__` en
listant les fichiers du dossier:

```python
path = Path(__file__).parent.absolute()
__all__ = [f.stem for f in path.iterdir()
           if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"]
```

Résultat: `from app.controllers import *` importe *tous* les controllers. Comme
une route (ou une table, ou une entrée du registre de l'injecteur, ou un seeder)
n'existe que si son module a été importé, ce mécanisme évite d'oublier un import
à chaque nouveau fichier.

### 2. Injection de dépendances

Un controller ne construit pas ses services, il les **déclare**:

```python
@app.get('/items')
@inject
def item_list(item_service: ItemService):
    ...
```

`@inject` lit les annotations de type et demande les instances à l'injecteur
(`app/framework/injector.py`). Et côté service, un décorateur suffit à le rendre
disponible — pas de fichier de configuration à tenir à jour:

```python
@injectable                                          # SINGLETON par défaut
class ItemService(BaseService): ...

@injectable(base=AuthService, scope=Scope.SCOPED)    # implémentation d'une interface
class AuthServiceImpl(AuthService): ...
```

Voir [08-injection-de-dependances.md](docs/08-injection-de-dependances.md).

### 3. Seeding auto-enregistré

```python
class ItemSeed(Seedable):
    order = 30

    def seed(self):
        ...
```

Créer le fichier dans `app/seed/` suffit: `from app.seed import *` l'importe,
`Seedable.__init_subclass__` enregistre la classe, et `Seed(app)` ajoute la route
`/seed` (en debug uniquement). Voir [12-seeding.md](docs/12-seeding.md).

---

## Les routes

| Méthode | URL | Vue | Accès |
|---|---|---|---|
| GET | `/` | `index` | tous |
| GET | `/items` | `item_list` | tous |
| GET | `/items/<id>` | `item_details` | tous |
| GET/POST | `/items/add` | `item_add` | ADMIN |
| GET/POST | `/items/<id>/edit` | `item_update` | ADMIN |
| POST | `/items/<id>/delete` | `item_delete` | ADMIN |
| GET/POST | `/register` | `register` | anonyme |
| GET/POST | `/login` | `login` | anonyme |
| GET | `/logout` | `logout` | tous |
| GET/POST | `/password/forgot` | `password_forgot` | anonyme |
| GET/POST | `/password/reset/<token>` | `password_reset` | porteur d'un token valide |
| GET | `/profile` | `profile` | connecté |
| GET | `/users` | `user_list` | ADMIN |
| GET | `/users/<id>` | `user_profile` | connecté |
| GET/POST | `/users/<id>/edit` | `user_update` | ADMIN **ou** soi-même |
| POST | `/users/<id>/delete` | `user_delete` | ADMIN |
| GET | `/basket` | `basket_details` | connecté |
| POST | `/basket/add` | `basket_add_item` | connecté |
| POST | `/basket/remove/<id>` | `basket_remove_item` | connecté |
| POST | `/basket/checkout` | `basket_checkout` | connecté |
| GET | `/baskets` | `basket_list` | ADMIN |
| GET | `/seed` | `seed` | debug uniquement |
| GET | `/jinja`, `/autre` | `test`, `test2` | démos Jinja des débuts |

Toute action qui modifie l'état est en **POST**, jamais en GET: un lien est
suivi par les navigateurs et les robots (préchargement, aperçus), un formulaire
non.

---

## Conventions de code du projet

- **Nommage des colonnes**: `snake_case`, préfixe de table pour les
  identifiants (`user_id`, `item_id`), pas de préfixe pour le reste
  (`username`, `name`, `stock`). Les tables sont au pluriel (`users`,
  `basket_items`).
- **Retours des services**: des DTO. Les méthodes qui rendent une entité sont
  suffixées `_entity` (`find_one_entity`) et réservées aux appels internes.
- **Un fichier = une classe** dans `models/`, `dtos/`, `mappers/`, `services/`,
  `forms/`, `seed/`.
- **Commentaires en français**, comme le reste de la formation.
- Les messages destinés à l'utilisateur passent par `flash()`, jamais par une
  variable de template dédiée.

---

## Aller plus loin

- La même application en version **API JSON** (JWT, `jsonify`, appels AJAX):
  <https://github.com/phil-form/pythonORM>. Comparer les deux est instructif:
  modèles, DTO, mappers et services sont quasi identiques, seuls les controllers
  et l'authentification changent. C'est précisément le but du découpage en
  couches.
- Les [exercices](docs/13-exercices.md) pour ajouter une entité de bout en bout.

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.
