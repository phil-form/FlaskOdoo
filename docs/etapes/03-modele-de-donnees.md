# Étape 03 — Le modèle de données

Une boutique: des utilisateurs qui ont des rôles, un catalogue d'articles, et des
paniers qui contiennent des articles en quantité. Six entités, et surtout des
**relations** — c'est là que se joue la qualité d'un modèle.

Cette étape ajoute aussi une page catalogue… écrite volontairement « mal », pour
justifier l'étape suivante.

---

## Démarrer

```bash
docker compose up -d db-example
pip install -r requirements.txt
./sqlAlchemy.sh -u          # applique DEUX migrations maintenant
python main.py
```

Puis `/seed` (les 4 seeders passent dans l'ordre `RoleSeed`, `UserSeed`,
`ItemSeed`, `BasketSeed`), et `/items`.

---

## Ce qui change

| Fichier | Changement |
|---|---|
| `app/models/base_entity.py` | **nouveau** — mixin: `created_at`, `updated_at`, `deleted_at`, `active` |
| `app/models/role.py`, `user_role.py` | **nouveaux** — les rôles et la table d'association |
| `app/models/item.py`, `basket.py`, `basket_item.py` | **nouveaux** — le catalogue et les paniers |
| `app/models/user.py` | + `email`, `description`, relations, méthodes métier |
| `migrations/versions/2b86203c0955_*.py` | **nouveau** — 5 tables + les colonnes de `BaseEntity` |
| `app/seed/*.py` | 4 seeders: rôles, users, articles, paniers |
| `app/controllers/home_controller.py` | **nouveau** — la route `/` (l'ancienne devient `/jinja`) |
| `app/controllers/item_controller.py` | **nouveau** — `/items` et `/items/<id>` |
| `app/templates/items/`, `home/jinja.html` | **nouveaux** |

### 1. Un mixin pour les colonnes techniques

```python
class BaseEntity:                     # PAS db.Model: aucune table
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    deleted_at = db.Column(db.DateTime(timezone=True))
    active = db.Column(db.Boolean, nullable=False, default=True,
                       server_default=db.true())
```

SQLAlchemy recopie ces colonnes dans chaque modèle qui hérite du mixin. Les six
tables ont donc le même socle sans duplication.

`active` + `deleted_at` = **soft delete**: on marque au lieu de supprimer, ce qui
garde l'historique cohérent. En contrepartie, il faut penser à filtrer
(`filter_by(active=True)`) partout.

### 2. one-to-many: la clé étrangère est du côté « many »

```python
class Basket(BaseEntity, db.Model):
    user_id = db.Column(db.ForeignKey('users.user_id'))        # <- la colonne
    user = db.relationship("User", back_populates="baskets")   # <- l'attribut Python

class User(BaseEntity, db.Model):
    baskets = db.relationship('Basket', back_populates='user',
                              cascade='all, delete-orphan')
```

- `db.Column(db.ForeignKey(...))` = une **colonne** réelle, une contrainte en base.
- `db.relationship(...)` = un **attribut Python**, aucune colonne. C'est lui qui
  permet `basket.user.username` ou de boucler sur `user.baskets`.
- `back_populates` synchronise les deux côtés en mémoire.
- Le nom de la classe cible est une **chaîne** (`"User"`): SQLAlchemy résout les
  noms à la fin des imports, ce qui évite les imports circulaires.

### 3. many-to-many *avec données*: une entité d'association

`UserRole` et `BasketItem` ne sont pas de simples tables de liaison: elles
portent des données (les dates de `BaseEntity`, la `quantity`). On en fait donc
des entités, avec une **clé primaire composée**:

```python
class BasketItem(BaseEntity, db.Model):
    item_id = db.Column(db.ForeignKey('items.item_id'), primary_key=True)
    basket_id = db.Column(db.ForeignKey('baskets.basket_id'), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
```

Conséquence: `user.roles` contient des `UserRole`, pas des `Role`. Pour les noms,
on traverse: `[ur.role.role_name for ur in self.roles]`.

### 4. Les cascades

```python
roles = db.relationship('UserRole', back_populates='user',
                        cascade='all, delete-orphan')
```

- `all`: `db.session.add(user)` insère aussi ses `UserRole` et ses paniers;
- `delete-orphan`: retirer un enfant de la collection le supprime en base — c'est
  ce qui fait fonctionner `basket.items.remove(ligne)`.

Sans cascade, supprimer un user qui a des rôles échoue: la base refuse de laisser
des lignes orphelines.

### 5. La logique métier va dans le modèle

```python
class Basket(BaseEntity, db.Model):
    def add_item(self, item, quantity):
        basket_item = self.find_item(item)
        exist = True
        if basket_item is None:
            exist = False
            basket_item = BasketItem()
            basket_item.item = item
            basket_item.basket = self
            self.items.append(basket_item)
        basket_item.quantity = quantity
        return basket_item, exist
```

Remarquez ce que la méthode ne fait **pas**: ni `db.session`, ni `commit`. Le
modèle manipule des objets; qui décide de la transaction viendra plus tard. Et
`BasketSeed` réutilise cette méthode au lieu de réinventer la règle.

### 6. La migration, ajustée à la main

`./sqlAlchemy.sh -m` avait produit:

```python
batch_op.add_column(sa.Column('email', sa.String(120), nullable=False))
```

… ce qui échoue si la table `users` contient déjà des lignes (celles insérées par
`/seed` à l'étape 02!). Alembic compare deux schémas, il ne connaît rien aux
données. D'où la recette en trois temps, visible dans la migration:

```python
op.add_column('users', sa.Column('email', sa.String(120), nullable=True))   # 1
op.execute("UPDATE users SET email = username || '@example.local' ...")     # 2
op.alter_column('users', 'email', nullable=False)                           # 3
```

C'est la réponse à l'exercice 2 de l'étape 01.

### 7. Le défaut assumé de cette étape

`item_controller.py` requête la base directement et passe des **entités** au
template:

```python
@app.get('/items')
def item_list():
    items = Item.query.filter_by(active=True).order_by(Item.item_id).all()
    return render_template('items/list.html', items=items)
```

Deux problèmes:

1. accéder à une relation depuis le template déclencherait une requête SQL en
   pleine page (et une `DetachedInstanceError` si la session est fermée);
2. le template connaît le schéma: renommer une colonne casse toutes les vues.

C'est exactement ce que l'étape 04 corrige.

---

## Exercices

### 1. Explorer les relations

Dans un shell Python (`python`, puis les imports), après un `/seed`:

```python
from app import app
from app.models.user import User
with app.app_context():
    u = User.query.filter_by(username='admin').first()
    print(u.role_names(), u.is_admin())
    print(u.baskets, u.current_basket())
```

- Combien de requêtes SQL `u.role_names()` déclenche-t-il ? (Activez l'écho SQL:
  `app.config['SQLALCHEMY_ECHO'] = True`.)
- Sur `/`, ouvrez la Debug Toolbar → onglet SQLAlchemy. Que se passerait-il avec
  200 articles affichant chacun leur catégorie ? Cherchez « problème N+1 ».

### 2. Une entité de plus: `Category`

Un article appartient à une catégorie.

1. `app/models/category.py`: `category_id`, `name` (unique, indexé), et
   `items = db.relationship('Item', back_populates='category')`;
2. dans `Item`: la clé étrangère + `category = db.relationship(...)`;
3. `./sqlAlchemy.sh -m "categories"`, **relisez** la migration, puis `-u`;
4. `app/seed/category_seed.py` avec `order = 25`, et rattachez une catégorie aux
   articles dans `ItemSeed`.

Vérification: `/seed` doit lister 5 seeders, dans le bon ordre.

### 3. Comprendre les cascades

```python
with app.app_context():
    from app import db
    from app.models.user import User
    u = User.query.filter_by(username='test').first()
    db.session.delete(u)
    db.session.commit()
```

- Que sont devenus ses `user_roles` et ses paniers ?
- Retirez `cascade='all, delete-orphan'` de `User.roles` et refaites l'essai:
  lisez l'erreur PostgreSQL, elle est très parlante.
- Remettez la cascade.

### 4. Soft delete

`BaseEntity.soft_delete()` existe mais personne ne l'appelle encore.

- Ajoutez une route `POST /items/<id>/desactiver` qui appelle `soft_delete()`.
- L'article disparaît-il de `/items` ? Pourquoi ?
- Quel inconvénient voyez-vous à ce que la contrainte unique sur `name` reste
  active pour un article désactivé ?

---

## Pour aller plus loin

- `../09-projet-final/docs/03-modeles-et-relations.md`
- `../09-projet-final/docs/04-migrations.md`

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`04-couches-metier-et-crud`](../04-couches-metier-et-crud/) — DTO, mappers,
services et formulaires: sortir les requêtes SQL des controllers et arrêter de
donner des entités aux templates.
