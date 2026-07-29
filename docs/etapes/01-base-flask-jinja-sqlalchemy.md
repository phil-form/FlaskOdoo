# Étape 01 — Flask, Jinja2 et SQLAlchemy

**Point de départ de la formation.** C'est l'état du dépôt tel qu'il a été
construit en cours: une application Flask minimale, des templates Jinja2, une
base PostgreSQL pilotée par SQLAlchemy et Alembic.

Rien n'est à jeter dans cette étape — tout ce qui suit s'appuie dessus.

---

## Démarrer

```bash
docker compose up -d db-example        # PostgreSQL sur le port 5435
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./sqlAlchemy.sh -u                     # crée la table users
python main.py                         # http://localhost:8080
```

| URL | Ce qu'elle fait |
|---|---|
| <http://localhost:8080/> | la démo Jinja: 10 nombres au hasard, seuls les pairs sont affichés |
| <http://localhost:8080/autre> | une vue qui renvoie du HTML sans template |
| <http://localhost:8080/seed> | insère les utilisateurs de démonstration (`admin`/`admin`, `test`/`test`) |

---

## Ce qu'il y a dans le projet

```
main.py                     lance le serveur de développement
docker-compose.yml          PostgreSQL (+ un service app, optionnel)
.env                        DATABASE_URL
sqlAlchemy.sh               raccourcis pour les migrations
migrations/                 Alembic: une migration, qui crée `users`
app/
├── __init__.py             création de l'app, des extensions, et la route /seed
├── controllers/
│   ├── __init__.py         auto-découverte des controllers
│   └── test_controller.py  les routes / et /autre
├── models/
│   ├── __init__.py         auto-découverte des modèles
│   ├── user.py             l'entité User
│   └── LiItem.py           un objet Python jetable, pour la démo Jinja
├── seed/
│   ├── __init__.py         __all__ = [UserSeed]  <- liste tenue à la main
│   └── user_seed.py        insère admin et test
├── framework/
│   └── seedable.py         la classe abstraite Seedable
└── templates/
    ├── layout/main_layout.html
    └── home/home.html
```

### 1. L'auto-découverte des modules

`app/models/__init__.py` et `app/controllers/__init__.py` construisent leur
`__all__` en listant les fichiers du dossier:

```python
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]
```

Du coup `from app.controllers import *` (en bas de `app/__init__.py`) importe
*tous* les controllers. C'est important: **une route n'existe pour Flask que si
le module qui contient son `@app.route` a été importé**. Idem pour les modèles,
que SQLAlchemy doit connaître pour générer les migrations.

Ajouter un controller ou un modèle = créer un fichier. Rien d'autre.

### 2. L'ordre dans `app/__init__.py`

```python
app = Flask("app")
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app.controllers import *      # <- en BAS du fichier
from app.models import *
```

Ces imports violent PEP8 volontairement: `test_controller.py` fait
`from app import app`, donc l'objet `app` doit déjà exister au moment de
l'import. C'est l'import circulaire classique d'une application Flask construite
autour d'un objet `app` global.

### 3. La route `/seed`

```python
@app.get('/seed')
def seed():
    import app.seed as seed

    for s in seed.__all__:          # __all__ = [UserSeed]
        c = s()
        if isinstance(c, Seedable):
            c.seed()
```

Ça marche, mais regardez `app/seed/__init__.py`:

```python
from app.seed.user_seed import UserSeed
__all__ = [UserSeed]
```

**La liste est tenue à la main.** Chaque nouveau seeder demande deux
modifications: créer le fichier, puis penser à l'ajouter ici. Et la route de
seeding est mélangée avec la configuration de l'application, alors qu'elle n'a
rien à y faire. C'est le sujet de l'étape 02.

### 4. Les migrations

```bash
./sqlAlchemy.sh -u                    # applique les migrations (flask db upgrade)
./sqlAlchemy.sh -m "nom_migration"    # en génère une nouvelle
```

`migrations/versions/f4908d7d2d8d_init.py` crée la table `users`. Alembic garde
la révision courante dans une table `alembic_version` et en déduit ce qui reste à
appliquer.

---

## Exercices

### 1. Prendre ses repères

- Lancez l'application, ouvrez `/`, puis modifiez `home.html` pour afficher les
  nombres **impairs**.
- Dans `test_controller.py`, ajoutez une route `/salut/<prenom>` qui affiche
  « Bonjour \<prenom\> » dans un template. Ajoutez-y un lien depuis la navbar
  avec `url_for` (jamais d'URL en dur).
- Ouvrez la Debug Toolbar (le panneau à droite): combien de requêtes SQL la page
  `/` déclenche-t-elle ? Et `/seed` ?

### 2. Un modèle et une migration

Ajoutez une colonne `email` à `User`:

1. modifiez `app/models/user.py`;
2. `./sqlAlchemy.sh -m "ajout email user"`;
3. **lisez le fichier généré** dans `migrations/versions/` — Alembic y écrit
   lui-même `please adjust!`;
4. `./sqlAlchemy.sh -u`.

Question: que se passe-t-il si vous mettez `nullable=False` alors que la table
contient déjà des utilisateurs ? Essayez, lisez l'erreur PostgreSQL, et
réfléchissez à la manière de vous en sortir. (La recette est appliquée à l'étape
03, et expliquée dans `../09-projet-final/docs/04-migrations.md`.)

### 3. Un deuxième seeder

Créez `app/seed/item_seed.py` avec une classe `ItemSeed(Seedable)` qui insère
trois articles — il faudra donc aussi un modèle `Item` et une migration. Faites
en sorte que `/seed` l'exécute.

Combien de fichiers avez-vous dû modifier pour que ce seeder s'exécute ?
Gardez la réponse en tête: **c'est le problème que résout l'étape 02.**

### 4. Casser, puis comprendre

- Renommez `test_controller.py` en `home_controller.py`. L'application
  fonctionne-t-elle toujours ? Pourquoi ?
- Supprimez la ligne `from app.models import *` de `app/__init__.py`, puis
  lancez `./sqlAlchemy.sh -m "test"`. Que contient la migration générée ?
  (Supprimez-la ensuite, et remettez la ligne.)

---

## Deux corrections déjà appliquées

Le dépôt d'origine ne pouvait pas démarrer tel quel: `requirements.txt` ne
contenait ni le driver PostgreSQL, ni la bibliothèque de hachage utilisée par
`user_seed.py`. Deux lignes ont donc été ajoutées:

```
psycopg2-binary==2.9.12   # sinon: ModuleNotFoundError: No module named 'psycopg2'
argon2-cffi==25.1.0       # sinon: ModuleNotFoundError: No module named 'argon2'
```

Réflexe utile: quand un projet ne démarre pas, la première question est « est-ce
que toutes les dépendances sont déclarées ? ».

Le fichier `readme.md` (minuscules) est l'aide-mémoire d'origine: il décrit
l'architecture **cible**, celle que la formation va construire. Vous pouvez le
lire comme un plan.

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`02-framework-de-seeding`](../02-framework-de-seeding/) — faire en sorte qu'un
seeder n'ait plus besoin d'être déclaré nulle part, et réserver `/seed` au mode
debug.
