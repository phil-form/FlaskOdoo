# 13 — Exercices

## Exercice 0 — Faire tourner le projet

1. Démarrer la base: `docker compose up -d db-example`
2. Installer les dépendances, appliquer les migrations (`./sqlAlchemy.sh -u`)
3. Lancer `python main.py`, visiter `/seed`, se connecter en `admin` / `admin`
4. Ouvrir la Debug Toolbar (onglet SQLAlchemy) et compter les requêtes de la page
   `/items`. Puis celles de `/users`. Que remarquez-vous ? (indice: N+1, voir
   [03-modeles-et-relations.md](03-modeles-et-relations.md))
5. Mettre `DEBUG=False` dans `.env.local`, relancer, appeler `/seed`. Expliquer le
   404.

---

## Exercice 1 — Une nouvelle entité de bout en bout: `Category`

Objectif: chaque article appartient à une catégorie. Le parcours complet des
couches, dans l'ordre.

**1. Le modèle** — `app/models/category.py`

```python
class Category(BaseEntity, db.Model):
    __tablename__ = "categories"
    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)
    items = db.relationship('Item', back_populates='category')
```

Puis, dans `Item`, ajouter la clé étrangère et la relation inverse (la FK va du
côté « many »):

```python
category_id = db.Column(db.ForeignKey('categories.category_id'))
category = db.relationship('Category', back_populates='items')
```

**2. La migration**

```bash
./sqlAlchemy.sh -m "categories"
```

Relire le fichier généré. `category_id` est-il nullable ? Si vous le voulez NOT
NULL alors que des articles existent déjà, appliquez la recette en trois temps de
[04-migrations.md](04-migrations.md).

**3. Le DTO** — `app/dtos/category_dto.py`, sur le modèle de `RoleDTO`. Puis
ajouter la catégorie à `ItemDTO` (attention: `build_from_entity` gère `Item` **et**
`BasketItem`, donc deux branches à compléter).

**4. Le service** — `app/services/category_service.py`. Copier `ItemService` et
retirer ce qui ne sert pas. Ne pas oublier `find_all_entities()` pour les choix du
formulaire.

**5. L'injecteur** — rien à configurer, juste un décorateur sur la classe:

```python
@injectable
class CategoryService(BaseService): ...
```

(SINGLETON par défaut, ce qui convient à un service sans état.)

**6. Le formulaire** — ajouter un `SelectField('Catégorie', coerce=int)` à
`ItemForm`, avec les `choices` remplies dans `__init__` (voir `UserUpdateForm`).

**7. Le mapper** — reporter le champ dans `ItemMapper.form_to_entity`.

**8. Les templates** — afficher la catégorie dans `items/_item_table.html` et
`items/details.html`, et le champ dans `items/add_or_update.html`.

**9. Le seed** — `app/seed/category_seed.py` avec `order = 25` (après les users,
avant les items), et rattacher une catégorie à chaque article dans `ItemSeed`.

**Vérification**: `/seed` doit annoncer `RoleSeed, UserSeed, CategorySeed,
ItemSeed, BasketSeed` et aucune erreur.

---

## Exercice 2 — Filtrer le catalogue par catégorie

- Route: `GET /items?category=3`
- Lire le paramètre avec `request.args.get('category', type=int)`
- Le **service** fait le filtrage (`find_all(category_id=None)`), pas le
  controller, et surtout pas le template
- Afficher des liens de filtre dans `items/list.html`, avec
  `url_for('item_list', category=c.category_id)`

Question: pourquoi ce filtre est-il en GET, alors que l'ajout au panier est en
POST ?

---

## Exercice 3 — Empêcher le dépassement de stock

Aujourd'hui, `BasketService.add_item()` ramène silencieusement la quantité au
stock disponible. Améliorations:

1. Prévenir l'utilisateur (`flash`) quand la quantité a été réduite. Attention: le
   service ne doit pas appeler `flash()` (il ne connaît pas HTTP) — que
   retourner pour que le controller le fasse ?
2. Refuser complètement l'ajout d'un article dont le stock est 0.
3. Au `checkout`, revérifier les stocks: entre l'ajout au panier et la validation,
   quelqu'un d'autre a pu commander. Que doit-il se passer ?

---

## Exercice 4 — Un rôle intermédiaire `MANAGER`

Un MANAGER peut créer et modifier des articles, mais pas les supprimer ni gérer
les utilisateurs.

1. Ajouter le rôle dans `RoleSeed`
2. Changer les décorateurs concernés dans `item_controller.py`
3. Problème: `@auth_required(level="MANAGER")` refuserait un ADMIN qui n'a pas
   aussi le rôle MANAGER… Regardez la règle « un ADMIN passe partout » du
   décorateur et expliquez pourquoi elle est là.
4. Question de conception: accepter une **liste** de niveaux
   (`@auth_required(level=["MANAGER", "ADMIN"])`) serait-il plus clair ?
   Implémentez-le.

---

## Exercice 5 — Historique de commande complet

Le panier validé ne conserve que les quantités. Faites-en une vraie commande:

1. Ajouter un prix à `Item` (`db.Numeric(10, 2)` — pourquoi pas `db.Float` pour de
   l'argent ?)
2. Ajouter `unit_price` à `BasketItem`, **copié au moment de l'ajout au panier**.
   Pourquoi ne pas simplement lire `item.price` à l'affichage de l'historique ?
3. Afficher un total par commande dans `baskets/details.html` (méthode du DTO, pas
   de calcul dans le template)

---

## Exercice 6 — Tests automatisés

Le projet n'a pas de tests: ajoutez-en.

```python
# tests/conftest.py
import pytest
from app import app as flask_app, db

@pytest.fixture
def client():
    flask_app.config['WTF_CSRF_ENABLED'] = False        # pas de jeton dans les tests
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'   # base en mémoire
    with flask_app.app_context():
        db.create_all()
        yield flask_app.test_client()
        db.drop_all()
```

À couvrir en priorité (ce sont les endroits où une erreur est silencieuse):

- un anonyme sur `/basket` est redirigé vers `/login`
- un simple USER ne peut pas ouvrir `/users`
- un simple USER ne peut pas éditer le profil d'un autre
- poster `roles=<id ADMIN>` en tant que USER ne donne pas le rôle
- un POST sans jeton CSRF est refusé (400)
- `/login?next=https://evil.example` ne redirige pas vers l'extérieur
- `/seed` deux fois de suite ne crée pas de doublons
- `/password/forgot` répond la même chose pour une adresse connue et inconnue
- un lien de réinitialisation déjà utilisé ne fonctionne plus (indice: quelle
  partie du token devient invalide ?)

Question: pourquoi une base SQLite en mémoire pour les tests, alors que
l'application tourne sur PostgreSQL ? Quelles différences pourraient masquer un
bug (indice: `batch_alter_table`, types, contraintes différées) ?

---

## Exercice 7 — Étendre le framework maison

Les trois automatismes du projet (découverte par `__all__`, `@injectable`,
`Seedable`) sont écrits à la main, en une centaine de lignes. Complétez-les:

1. **Un décorateur `@transactional`** sur une méthode de service: commit à la
   sortie, rollback si une exception remonte. Les services n'auraient alors plus
   leur `try/except/rollback` répété.
2. **Un `Seedable` capable de se dé-seeder**: ajouter une méthode `unseed()` et
   une route `/unseed` (debug uniquement), exécutée dans l'ordre `order`
   **inverse** — pourquoi inverse ?
3. **Détecter les dépendances circulaires** dans l'injecteur: A demande B qui
   demande A donne aujourd'hui une récursion infinie. Où l'attraper, et
   qu'afficher ?
