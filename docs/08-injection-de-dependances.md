# 08 — Injection de dépendances

Fichiers: `app/framework/injector.py`,
`app/framework/decorators/injectable.py`, `app/framework/decorators/inject.py`

## Le problème

Sans injection, une vue construit ses dépendances:

```python
@app.get('/items')
def item_list():
    item_service = ItemService()          # la vue DÉCIDE de l'implémentation
    ...
```

Ennuis: impossible de remplacer `ItemService` par une version de test ou par une
autre implémentation sans éditer toutes les vues; une nouvelle instance à chaque
requête; et la vue connaît des détails qui ne la concernent pas.

Avec injection, la vue **déclare son besoin**:

```python
@app.get('/items')
@inject
def item_list(item_service: ItemService):
    return render_template('items/list.html', items=item_service.find_all())
```

Le « qui fournit quoi, et pour combien de temps » est déclaré **sur le service
lui-même**, avec un décorateur.

## Les trois pièces

### 1. La déclaration — `@injectable`

```python
@injectable                                          # -> ItemService, SINGLETON
class ItemService(BaseService): ...

@injectable(scope=Scope.TRANSIENT)                   # autre durée de vie
class MonService: ...

@injectable(base=AuthService, scope=Scope.SCOPED)    # implémentation d'une interface
class AuthServiceImpl(AuthService): ...
```

Se lit: « quand on demande **base** (par défaut la classe elle-même), fournis une
instance de cette classe, avec cette **durée de vie** (par défaut SINGLETON) ».

Le cas `AuthServiceImpl` est le plus intéressant: `base=AuthService` fait que les
controllers demandent l'**interface** (`auth_service: AuthService`) et reçoivent
l'implémentation. Pour passer à une authentification par JWT: on écrit
`AuthServiceJwt`, on y déplace le décorateur, et rien d'autre ne change.

Le décorateur ne modifie pas la classe: il l'inscrit dans un registre global et
la retourne telle quelle.

```python
def injectable(cls=None, *, base=None, scope: Scope = Scope.SINGLETON):
    def decorate(target):
        register_dependency(DependencyConfig(base or target, target, scope))
        return target

    if cls is None:        # appelé avec parenthèses: @injectable(scope=...)
        return decorate

    return decorate(cls)   # appelé nu: @injectable
```

Le double usage (avec et sans parenthèses) explique la forme du code: sans
parenthèses Python appelle `injectable(MaClasse)`, avec parenthèses il appelle
d'abord `injectable(scope=...)` qui doit **retourner** le vrai décorateur.
`base` et `scope` sont keyword-only (le `*`), sinon `@injectable(AuthService)`
serait indistinguable de `@injectable` posé sur la classe `AuthService`.

C'est exactement le mécanisme de `Seedable.__init_subclass__` pour les seeds
(voir [12-seeding.md](12-seeding.md)): la déclaration vaut enregistrement.

> **Avant**, ce projet avait un fichier `injector_config.py` qui listait chaque
> liaison à la main. Il a été supprimé: c'était une seconde liste à tenir à jour,
> et un service oublié n'échouait qu'à l'exécution, sous la forme d'un `None`
> silencieux passé à la vue.

### 2. Le conteneur — `injector.py`

```python
injector = Injector(app)                           # dans app/__init__.py
app.injector['UserService']                        # -> une instance
```

Le constructeur recopie le registre rempli par `@injectable`, puis s'accroche à
`app` (`app.injector = self`) parce que `app` est le seul objet global disponible
partout.

```python
def __init__(self, app: Flask, config=None):
    self.__config = ContainerConfig()

    for dependency in registered_dependencies():
        self.__config.bind(dependency)

    if config is not None:      # crochet facultatif, pour les tests
        config(self.__config)
```

Le paramètre `config` reste utile pour remplacer une dépendance par un double
dans un test, sans toucher au code de production:

```python
Injector(app, config=lambda c: c.bind(
    DependencyConfig(UserService, FakeUserService, Scope.SINGLETON)))
```

**Attention à l'ordre**: un service ne s'enregistre qu'à l'import de son module.
`app/__init__.py` fait donc `from app.services import *` (auto-découverte du
dossier, comme pour les modèles et les controllers) **avant** de créer
l'injecteur. Sans cet import, un service qu'aucun controller n'utilise
directement — `AuthServiceImpl`, justement — resterait inconnu.

### 3. Le décorateur — `inject.py`

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

Ce que ça fait: lire les **annotations de type** de la fonction
(`item_service: ItemService`), demander chaque type au conteneur, passer les
instances en `kwargs`.

Détails qui comptent:

- `if key == 'return'` — l'annotation de retour (`-> str`) est dans le même
  dictionnaire, ce n'est pas un paramètre.
- `if key in kwargs` — ne jamais écraser ce que Flask a déjà fourni depuis
  l'URL (`<int:item_id>`).
- `@wraps(func)` — recopie `__name__`, sans quoi Flask enregistrerait toutes les
  vues sous le nom `function_wrapper` et lèverait une erreur de endpoint
  dupliqué.
- Vu de Flask, la fonction décorée n'a plus de paramètre `item_service`: il
  n'essaiera donc pas de le remplir depuis l'URL.

### L'ordre des décorateurs

```python
@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])   # 1
@auth_required(level="ADMIN", or_is_current_user=True)             # 2
@inject                                                           # 3
def user_update(user_id: int, user_service: UserService, auth_service: AuthService):
```

Les décorateurs s'appliquent de bas en haut, donc `@app.route` doit être **en
haut**: il enregistre la fonction déjà décorée. Inversé, Flask enregistrerait la
fonction nue et l'injection ne se produirait jamais.

## Les scopes

```python
class Scope(Enum):
    SINGLETON = 1    # une instance pour tout le process
    SCOPED = 2       # une instance par requête HTTP
    TRANSIENT = 3    # une nouvelle instance à chaque demande
```

| Scope | Quand | Exemple |
|---|---|---|
| SINGLETON | service **sans état** | `ItemService`, `UserService` |
| SCOPED | garde une donnée liée à la requête ou à l'utilisateur | `AuthService` |
| TRANSIENT | objet qu'on ne veut jamais partager | (aucun ici) |

**Le choix n'est pas cosmétique.** `AuthServiceImpl` mémorise l'utilisateur
courant: en SINGLETON, la première requête chargerait Alice, et Bob verrait
l'identité d'Alice. Bug de sécurité, difficile à reproduire, et qui n'apparaît
que sous charge.

Inversement, mettre un service sans état en TRANSIENT ne casse rien mais crée des
objets inutiles.

### L'implémentation de SCOPED

```python
def __get_scoped(self, dependency):
    if not has_app_context():
        return self.__get_transient(dependency)     # hors requête: instance jetable

    scoped = g.setdefault('_injector_scoped', {})
    if scoped.get(dependency.base.__name__) is None:
        scoped[dependency.base.__name__] = dependency.implement()
    return scoped[dependency.base.__name__]
```

`g` est l'espace de stockage que Flask remet à zéro **à chaque requête**: c'est
exactement la définition d'un scope requête, et il est nettoyé automatiquement.

> Note pour ceux qui comparent avec la version d'origine du framework
> (dépôt `pythonORM`): celle-ci indexait un dictionnaire par valeur du cookie
> `session`. Deux défauts: le dictionnaire ne se vide jamais (fuite mémoire, et
> il grandit avec le nombre de visiteurs), et un visiteur anonyme n'a pas encore
> de cookie — tous partageaient donc la clé `None`, c'est-à-dire la même
> instance. `g` règle les deux problèmes.

## Injection dans un constructeur

```python
class AuthServiceImpl(AuthService):
    @inject
    def __init__(self, user_service: UserService):
        self.__user_service = user_service
```

`@inject` fonctionne sur n'importe quelle fonction, y compris `__init__`. C'est
ce qui permet à l'injecteur d'écrire `AuthServiceImpl()` sans argument tout en
lui fournissant son `UserService`.

Limite connue de cette implémentation minimaliste: elle ne détecte pas les
**dépendances circulaires** (A a besoin de B qui a besoin de A) — le résultat
serait une récursion infinie. Les vrais conteneurs (`dependency-injector`,
Spring…) construisent un graphe et refusent le cycle au démarrage.

## Utiliser l'injecteur hors d'une vue

Dans `app/__init__.py`, le *context processor* qui expose `current_user` aux
templates:

```python
@app.context_processor
def inject_current_user():
    from app.services.auth_service import AuthService
    auth_service = app.injector[AuthService.__name__]
    return {'current_user': auth_service.get_current_user()}
```

C'est l'accès direct par nom, sans décorateur. Notez l'import **à l'intérieur**
de la fonction: au moment où `app/__init__.py` s'exécute, le module des services
n'est pas forcément chargé; à l'exécution de la vue, il l'est.

## Pourquoi écrire ce framework à la main ?

Flask ne fournit volontairement rien de tout ça: c'est un micro-framework, il
donne le routage et les templates, et laisse le reste ouvert. Plutôt que
d'installer une bibliothèque (`dependency-injector`, `injector`, `svcs`...), on
écrit l'injecteur en 80 lignes — et on voit alors exactement ce qu'un framework
complet fait pour vous, au lieu de l'utiliser comme une boîte noire.

Ces mêmes idées reviennent dans les frameworks « tout inclus », dont Odoo:

| Ici, à la main | L'équivalent dans un framework complet |
|---|---|
| `app.injector['UserService']` | demander un objet à un registre par son nom (`self.env['res.partner']` en Odoo) |
| `@injectable`, `@inject` | des décorateurs qui déclarent, sans écrire de code d'assemblage |
| `__all__` + `import *` | la découverte automatique des modules/addons installés |
| `Seedable` + `/seed` | les fichiers de données de démonstration d'un module |

L'idée à retenir est toujours la même: **on déclare ce dont on a besoin,
l'infrastructure décide ce qu'on reçoit et quand**. C'est ce réflexe qui sert
ensuite, quel que soit l'outil.
