# Étape 02 — Un framework de seeding

À l'étape précédente, ajouter un jeu de données demandait de créer un fichier
**et** de penser à l'inscrire dans `app/seed/__init__.py`. Une liste tenue à la
main finit toujours par être fausse.

Ici on écrit le premier morceau du framework maison: un seeder s'enregistre tout
seul, il suffit que son fichier existe. Et la route `/seed` disparaît en
production.

> Nouveauté également: `DEBUG` vient maintenant du `.env` au lieu d'être codé en
> dur dans `app/__init__.py`.

---

## Démarrer

```bash
docker compose up -d db-example
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py                         # http://localhost:8080
```

`http://localhost:8080/seed` affiche maintenant une vraie page de compte rendu:
les seeders exécutés, et ceux qui ont échoué.

---

## Ce qui change

| Fichier | Changement |
|---|---|
| `app/framework/seed/seedable.py` | `Seedable` s'auto-enregistre, et gagne un attribut `order` |
| `app/framework/seed/seed.py` | **nouveau** — la classe `Seed`: ajoute la route `/seed` (en debug) |
| `app/framework/seed/__init__.py` | **nouveau** — expose `Seedable` et `Seed` |
| `app/framework/seedable.py` | supprimé (déplacé dans `framework/seed/`) |
| `app/seed/__init__.py` | plus de liste à la main: auto-découverte par `__all__` |
| `app/__init__.py` | la route `/seed` disparaît d'ici, remplacée par `Seed(app)` |
| `app/templates/seed/seed.html` | **nouveau** — la page de compte rendu |
| `.env` | `DEBUG`, `SECRET_KEY`, `PORT` |

### 1. Une classe qui s'enregistre elle-même

```python
class Seedable(ABC):
    order: int = 100
    __seeders: dict[str, type["Seedable"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if getattr(cls.seed, "__isabstractmethod__", False):
            return          # sous-classe encore abstraite: pas un seeder

        Seedable.__seeders[f"{cls.__module__}.{cls.__qualname__}"] = cls
```

`__init_subclass__` est un *hook* du langage: Python l'appelle sur la classe
parente **chaque fois qu'une sous-classe est déclarée**. Dès que l'interpréteur
lit `class UserSeed(Seedable):`, la classe est inscrite. Pas de décorateur, pas
d'instanciation, pas de liste.

Deux détails qui comptent:

- le test `__isabstractmethod__` écarte les classes intermédiaires qui
  n'implémentent pas `seed()`;
- la clé du registre est `module.Classe`: si un module est rechargé (le reloader
  du mode debug le fait), on remplace l'entrée au lieu d'en créer une deuxième.

### 2. L'import qui déclenche l'enregistrement

Un enregistrement n'a lieu que si le module est **importé**. `app/seed/__init__.py`
utilise donc le même mécanisme que les modèles et les controllers:

```python
path = Path(__file__).parent.absolute()
__all__ = [f.name[:-3] for f in path.iterdir() if f.is_file() and f.name.endswith(".py")]
```

et dans `app/__init__.py`:

```python
from app.seed import *
from app.framework.seed import Seed

seed = Seed(app)
```

> Attention: `from app.seed import *`, **jamais** `import app.seed`. Cette
> deuxième forme lie le nom `app` au *package* et écrase la variable `app`,
> l'objet Flask: toutes les lignes suivantes qui font `app.logger` ou
> `app.config` casseraient.

### 3. Une route réservée au debug

```python
class Seed:
    def __init__(self, app: Flask, route: str = "/seed"):
        self.__app = app

        if not app.debug:
            app.logger.info(f"Seed: {route} non enregistrée (application hors debug)")
            return

        app.add_url_rule(route, "seed", self.__seed, methods=["GET"])
```

- Une URL qui réinjecte des données de test ne doit **pas exister** en
  production. Hors debug, elle renvoie un 404 — pas une page « accès refusé »,
  qui révélerait son existence.
- `add_url_rule(règle, endpoint, fonction)` remplace `@app.get(...)`: un
  décorateur ne peut pas être posé sur une méthode (il enregistrerait une
  fonction attendant `self`). `self.__seed` est une méthode liée, elle transporte
  son `self`.
- `Seedable.seeders()` reste utilisable hors HTTP (script, CLI), puisque
  l'enregistrement dépend de l'import et pas du debug.

### 4. `order` et idempotence

```python
@staticmethod
def seeders():
    return sorted(Seedable.__seeders.values(), key=lambda seeder: seeder.order)
```

Sans cet ordre, les seeders passeraient dans l'ordre alphabétique des fichiers.
Numéroter de 10 en 10 permet d'en insérer un entre deux.

Et chaque seeder vérifie avant d'insérer:

```python
if User.query.filter_by(username=username).first() is not None:
    continue
```

Sans ça, le deuxième passage sur `/seed` violerait la contrainte unique et
**tout** le seeding échouerait.

### 5. `DEBUG` dans le `.env`

```python
app.debug = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")
```

Pourquoi si verbeux ? Parce qu'une variable d'environnement est **toujours une
chaîne**: `bool(os.environ.get("DEBUG"))` vaut `True` même pour `DEBUG=False`.
C'est un piège classique.

---

## Exercices

### 1. Vérifier l'automatisme

- Créez `app/seed/zz_test_seed.py` avec un seeder qui écrit simplement
  `app.logger.debug("coucou")`. Rechargez `/seed`: il doit apparaître dans la
  liste **sans que vous ayez touché à un autre fichier**.
- Donnez-lui `order = 5`. Où passe-t-il dans la liste ?
- Supprimez le fichier. Que se passe-t-il ?

### 2. Le mode debug

- Mettez `DEBUG=False` dans un `.env.local`, relancez, appelez `/seed`.
  Vous devez obtenir un **404**. Pourquoi 404 et pas 403 ?
- Toujours en `DEBUG=False`, vérifiez dans un shell Python que les seeders sont
  quand même enregistrés:
  ```python
  from app import app
  from app.framework.seed import Seedable
  print([s.__name__ for s in Seedable.seeders()])
  ```
  Pourquoi est-ce souhaitable ?

### 3. Faire échouer proprement

Écrivez un seeder qui lève volontairement une exception
(`raise Exception("boum")`). Rechargez `/seed`.

- Les autres seeders s'exécutent-ils quand même ?
- Où retrouvez-vous l'erreur ? (Regardez la page **et** la console.)
- Où est le `try/except` qui rend ça possible ?

### 4. Anticiper la suite

Le modèle `User` n'a pour l'instant que `username` et `password`. Écrivez au
brouillon les modèles nécessaires à une boutique: rôles, articles, paniers.

- Comment relier un utilisateur à **plusieurs** rôles, et un rôle à plusieurs
  utilisateurs ?
- Où mettre la quantité d'un article dans un panier ?

L'étape 03 donne une réponse — comparez-la à la vôtre.

---

## Pour aller plus loin

`../09-projet-final/docs/12-seeding.md` (le mécanisme en détail, y compris un
piège d'autoflush SQLAlchemy rencontré en écrivant `UserSeed`).

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`03-modele-de-donnees`](../03-modele-de-donnees/) — le modèle complet:
`BaseEntity`, relations one-to-many et many-to-many, cascades, et une deuxième
migration.
