# Étape 05 — Injection de dépendances

Deuxième morceau du framework maison. Le code de l'application ne change presque
pas — ce qui change, c'est **qui décide** de fournir les services, et pour
combien de temps.

C'est une étape courte à lire et importante à comprendre: le même mécanisme
(registre + décorateurs) revient dans tous les frameworks « tout inclus », Odoo
compris.

---

## Démarrer

```bash
docker compose up -d db-example
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py
```

Les pages sont identiques à l'étape 04. C'est normal: c'est un refactoring.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/framework/injector.py` | **nouveau** — le conteneur, les scopes, le registre |
| `app/framework/decorators/injectable.py` | **nouveau** — déclarer une classe injectable |
| `app/framework/decorators/inject.py` | **nouveau** — injecter dans une fonction |
| `app/services/item_service.py` | + `@injectable` |
| `app/services/__init__.py` | auto-découverte (indispensable, voir plus bas) |
| `app/controllers/*.py` | les vues déclarent leurs services au lieu de les créer |
| `app/__init__.py` | + `from app.services import *` puis `Injector(app)` |

### Avant / après

```python
# étape 04
item_service = ItemService()          # le controller choisit l'implémentation

@app.get('/items')
def item_list():
    return render_template('items/list.html', items=item_service.find_all())
```

```python
# étape 05
@app.get('/items')
@inject
def item_list(item_service: ItemService):
    return render_template('items/list.html', items=item_service.find_all())
```

La vue **déclare son besoin**; quelqu'un d'autre décide ce qu'elle reçoit.

### 1. `@injectable`: déclarer

```python
@injectable                                          # SINGLETON par défaut
class ItemService(BaseService): ...

@injectable(scope=Scope.TRANSIENT)                   # autre durée de vie
class MonService: ...

@injectable(base=AuthService, scope=Scope.SCOPED)    # une interface (étape 06)
class AuthServiceImpl(AuthService): ...
```

Le décorateur inscrit la classe dans un registre global et la retourne
**inchangée**. C'est le même principe que `Seedable.__init_subclass__` à l'étape
02: déclarer vaut enregistrer, il n'y a aucun fichier de configuration à tenir à
jour.

Sa forme mérite un coup d'œil, parce qu'il fonctionne avec et sans parenthèses:

```python
def injectable(cls=None, *, base=None, scope: Scope = Scope.SINGLETON):
    def decorate(target):
        register_dependency(DependencyConfig(base or target, target, scope))
        return target

    if cls is None:        # appelé avec parenthèses: @injectable(scope=...)
        return decorate

    return decorate(cls)   # appelé nu: @injectable
```

`base` et `scope` sont *keyword-only* (le `*`): sinon `@injectable(AuthService)`
serait indistinguable de `@injectable` posé sur une classe nommée `AuthService`.

### 2. `@inject`: recevoir

```python
def inject(func):
    @wraps(func)
    def function_wrapper(*args, **kwargs):
        arguments = inspect.getfullargspec(func)

        for key, val in arguments.annotations.items():
            if key == 'return' or key in kwargs:
                continue
            to_inject = app.injector[val.__name__]
            if to_inject is not None:
                kwargs[key] = to_inject

        return func(*args, **kwargs)
    return function_wrapper
```

- il lit les **annotations de type** et demande chaque type au conteneur;
- `key in kwargs` protège ce que Flask a déjà fourni depuis l'URL
  (`<int:item_id>`);
- `@wraps` recopie `__name__`, sans quoi Flask enregistrerait toutes les vues
  sous le nom `function_wrapper`;
- vu de Flask, la fonction n'a plus de paramètre `item_service`: il n'essaiera pas
  de le remplir depuis l'URL.

**Ordre des décorateurs**: `@app.route` doit être **au-dessus** de `@inject`,
sinon Flask enregistre la fonction non décorée.

### 3. Les scopes

| Scope | Durée de vie | Pour qui |
|---|---|---|
| `SINGLETON` | une instance pour tout le process | service **sans état** (`ItemService`) |
| `SCOPED` | une instance par requête HTTP | service qui retient quelque chose de la requête (`AuthService`, étape 06) |
| `TRANSIENT` | une nouvelle instance à chaque demande | objet qu'on ne veut jamais partager |

Le choix n'est pas cosmétique: à l'étape 06, `AuthService` mémorise
l'utilisateur courant. En `SINGLETON`, le premier visiteur imposerait son identité
à tous les suivants — bug de sécurité, difficile à reproduire, et qui n'apparaît
que sous charge.

`SCOPED` s'appuie sur `flask.g`, l'espace de stockage que Flask remet à zéro à
chaque requête.

### 4. L'ordre d'initialisation, encore

Une classe ne s'enregistre qu'à l'**import** de son module. D'où, dans
`app/__init__.py`:

```python
from app.services import *          # les @injectable s'enregistrent...
from app.framework.injector import Injector

injector = Injector(app)            # ...avant que l'injecteur lise le registre
```

`app/services/__init__.py` a donc reçu le même `__all__` auto-découvert que
`models/`, `controllers/` et `seed/`. Sans cet import, un service qu'aucun
controller n'utilise directement resterait invisible — ce sera exactement le cas
de `AuthServiceImpl` à l'étape suivante.

---

## Exercices

### 1. Observer les scopes

Ajoutez temporairement une route de diagnostic:

```python
@app.get('/__probe')
@inject
def probe(item_service: ItemService):
    return f"{id(item_service)}"
```

- Rechargez plusieurs fois: l'identifiant change-t-il ? Pourquoi ?
- Passez `ItemService` en `@injectable(scope=Scope.TRANSIENT)` et refaites
  l'essai.
- Remettez `SINGLETON` et supprimez la route.

### 2. Casser l'ordre

- Dans `app/__init__.py`, déplacez `injector = Injector(app)` **avant**
  `from app.services import *`. Que se passe-t-il, et à quel moment
  (démarrage ? premier appel de page ?) — l'erreur est-elle explicite ?
- Inversez `@app.get('/items')` et `@inject`. Lisez l'erreur.

### 3. Substituer une implémentation

C'est tout l'intérêt de l'injection. Écrivez, dans un fichier de test:

```python
class FakeItemService(ItemService):
    def find_all(self):
        return []

Injector(app, config=lambda c: c.bind(
    DependencyConfig(ItemService, FakeItemService, Scope.SINGLETON)))
```

Vérifiez que `/items` affiche « Aucun article » sans que le code de la vue ait
changé. Pourquoi est-ce précieux pour les tests ?

### 4. Une limite du framework maison

Créez deux services qui se demandent mutuellement dans leur `__init__`
(A a besoin de B, B a besoin de A) et appelez-en un. Que se passe-t-il ?

Comment un vrai conteneur (Spring, `dependency-injector`) évite-t-il ça ?
Où faudrait-il l'attraper dans `injector.py` ?

---

## Pour aller plus loin

`../09-projet-final/docs/08-injection-de-dependances.md` — dont un tableau qui
met en regard chaque mécanisme maison et son équivalent dans un framework
complet (`self.env['res.partner']` en Odoo, par exemple).

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`06-authentification-et-roles`](../06-authentification-et-roles/) — enfin fermer
la porte: comptes, mots de passe hachés, session, rôles.
