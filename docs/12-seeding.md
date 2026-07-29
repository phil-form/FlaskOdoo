# 12 — Seeding

Fichiers: `app/framework/seed/seedable.py`, `app/framework/seed/seed.py`,
`app/seed/`

## À quoi ça sert

Repartir d'une base peuplée et cohérente, en une URL. Pratique pour une
démonstration, pour tester une page qui a besoin de données, ou pour repartir
proprement après avoir tout cassé.

Ce n'est **pas** un remplacement des migrations: une migration transforme le
*schéma* (et les données indispensables au fonctionnement), un seed insère des
données de *démonstration*.

## Écrire un seeder

```python
class ItemSeed(Seedable):
    order = 30

    def seed(self):
        for name, description, stock in self.ITEMS:
            if Item.query.filter_by(name=name).first() is not None:
                continue                        # idempotence
            db.session.add(Item(name=name, description=description, stock=stock))
        db.session.commit()
```

**C'est tout.** Pas d'import à ajouter ailleurs, pas de liste à mettre à jour, pas
de route à écrire. Il suffit que le fichier soit dans `app/seed/` et que la classe
hérite de `Seedable`.

## Comment l'automatisme fonctionne

Trois mécanismes s'enchaînent.

### 1. `__init_subclass__` — l'auto-enregistrement

```python
class Seedable(ABC):
    __seeders: dict[str, type["Seedable"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if getattr(cls.seed, "__isabstractmethod__", False):
            return                              # sous-classe encore abstraite

        Seedable.__seeders[f"{cls.__module__}.{cls.__qualname__}"] = cls
```

`__init_subclass__` est un *hook* du langage: Python l'appelle sur la classe
parente **à chaque fois qu'une sous-classe est déclarée**. Dès que l'interpréteur
lit `class ItemSeed(Seedable):`, la classe s'inscrit au registre. Aucune
instanciation, aucun décorateur.

Deux détails:

- Le test `__isabstractmethod__` écarte les sous-classes intermédiaires qui
  n'implémentent pas `seed()`: elles ne sont pas exécutables. (On ne peut pas
  utiliser `inspect.isabstract(cls)` ici: `ABCMeta` calcule
  `__abstractmethods__` *après* l'appel à `__init_subclass__`, la réponse serait
  fausse.)
- La clé du dictionnaire est `module.Classe`, pas la classe elle-même: si un
  module est rechargé (le reloader du mode debug le fait), on remplace l'entrée
  au lieu d'en ajouter une deuxième.

### 2. `__all__` — l'auto-import

Un enregistrement n'a lieu que si le module est **importé**. `app/seed/__init__.py`
utilise donc exactement le même mécanisme que les modèles, les controllers et les
services: construire `__all__` à partir du contenu du dossier.

```python
path = Path(__file__).parent.absolute()
__all__ = [f.stem for f in path.iterdir()
           if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"]
```

Et dans `app/__init__.py`, l'import en étoile déclenche les imports:

```python
from app.seed import *
from app.framework.seed import Seed

seed = Seed(app)
```

Pour un package, mettre des noms de **modules** dans `__all__` fait que
`from app.seed import *` les importe tous. C'est le même idiome partout dans le
projet — un seul mécanisme à comprendre pour les quatre dossiers.

> Historique: une version précédente de `Seed` faisait la découverte elle-même,
> avec `pkgutil.iter_modules()` + `importlib.import_module()`, et
> `Seed(app, __name__)` était instancié dans `app/seed/__init__.py`. Ça marchait,
> mais c'était un deuxième mécanisme de découverte à côté de celui des modèles.
> Un seul suffit.
>
> Attention au passage: dans `app/__init__.py`, il faut `from app.seed import *`
> (ou `from app import seed`), **jamais** `import app.seed` — cette dernière
> forme lie le nom `app` au *package* et écrase la variable `app`, l'objet Flask.
> Toutes les lignes suivantes qui font `app.logger` ou `app.config` casseraient.

### 3. `add_url_rule` — la route

```python
app.add_url_rule(route, "seed", self.__seed, methods=["GET"])
```

`@app.get('/seed')` ne peut pas décorer une **méthode** (le décorateur
enregistrerait une fonction attendant `self`). `add_url_rule(règle, endpoint,
fonction)` est la version explicite, et `self.__seed` est une méthode liée: elle
transporte son `self`.

`Seed` ne fait donc plus qu'une chose: exposer la route. La découverte, elle, est
déjà faite au moment où on l'instancie.

## La route n'existe qu'en debug

```python
def __init__(self, app: Flask, route: str = "/seed"):
    self.__app = app

    if not app.debug:
        app.logger.info(f"Seed: {route} non enregistrée (application hors debug)")
        return

    app.add_url_rule(route, "seed", self.__seed, methods=["GET"])
```

Une URL qui réinjecte des données de test ne doit pas exister en production:
n'importe qui pourrait l'appeler. Hors debug, la route renvoie donc un 404 — pas
une page « accès refusé » qui révélerait son existence.

L'enregistrement des seeders, en revanche, a toujours lieu — il dépend du
`from app.seed import *`, pas du debug. `Seedable.seeders()` reste donc utilisable
depuis un script ou une commande CLI, où l'on peut vouloir seeder sans passer par
HTTP.

## L'ordre d'exécution

```python
order: int = 100                      # dans Seedable

@staticmethod
def seeders():
    return sorted(Seedable.__seeders.values(), key=lambda seeder: seeder.order)
```

Sans cet ordre, les seeders passeraient dans l'ordre alphabétique des fichiers
(`basket_seed`, `item_seed`, `role_seed`, `user_seed`) — et `UserSeed` chercherait
des rôles qui n'existent pas encore.

| Seeder | `order` | Dépend de |
|---|---|---|
| `RoleSeed` | 10 | — |
| `UserSeed` | 20 | les rôles |
| `ItemSeed` | 30 | — |
| `BasketSeed` | 40 | les users et les items |

Numéroter de 10 en 10 permet d'insérer un seeder entre deux sans tout
renuméroter.

## Idempotence

Relancer `/seed` ne doit rien casser. Chaque seeder vérifie donc avant d'insérer:

```python
if Role.query.filter_by(role_name=role_name).first() is not None:
    continue
```

Sans ce test, le deuxième appel violerait la contrainte unique et **tout** le
seeding échouerait. `BasketSeed` obtient l'idempotence autrement: `add_item()`
met la quantité à jour au lieu de l'additionner.

## Tolérance aux pannes

```python
for seeder in Seedable.seeders():
    try:
        seeder().seed()
        seeded.append(seeder.__name__)
    except Exception as e:
        self.__app.logger.error(f"{seeder.__name__}: {e}")
        failed.append(f"{seeder.__name__} ({e})")
```

Un seeder en erreur n'empêche pas les suivants, et la page de retour
(`templates/seed/seed.html`) liste les deux colonnes: exécutés et en erreur. Utile
en formation — on voit tout de suite lequel a un problème.

## Réutiliser la logique métier

`BasketSeed` n'écrit pas de SQL et ne recrée pas la règle d'ajout au panier:

```python
basket = user.current_basket()
basket_item, exist = basket.add_item(item, quantity)

if not exist:
    db.session.add(basket_item)
```

Exactement ce que fait `BasketService.add_item()`. Si la règle change, elle change
à un seul endroit (le modèle). Un seed qui bricole ses propres INSERT finit
toujours par produire des données que l'application refuse.

## Un piège rencontré: l'autoflush

Version initiale de `UserSeed`:

```python
user = User(...)
for role_name in role_names:
    role = Role.query.filter_by(role_name=role_name).first()   # ← déclenche un autoflush
    user.add_role(role)
db.session.add(user)                                            # ← trop tard
```

SQLAlchemy émet:

```
SAWarning: Object of type <UserRole> not in session,
add operation along 'Role.users' will not proceed
```

Explication: chaque requête déclenche un *autoflush* (SQLAlchemy envoie les
changements en attente avant de lire, pour que la lecture les voie). Les `UserRole`
créés par `add_role()` ne sont rattachés à aucune session, puisque `db.session.add(user)`
n'a pas encore eu lieu — la liaison n'est donc pas insérée.

Correctif: `db.session.add(user)` **avant** la boucle. À partir de là, la cascade
sur `User.roles` fait entrer les `UserRole` dans la session au fur et à mesure.

Retenez le principe: attachez l'objet racine à la session tôt, avant de bâtir ses
relations.
