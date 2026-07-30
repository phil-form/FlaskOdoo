# 03 — Modèles & relations

Fichiers: `app/models/`

## Un modèle = une table

```python
class Item(BaseEntity, db.Model):
    __tablename__ = "items"

    item_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True, unique=True)
    description = db.Column(db.Text, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=1)
```

- `db.Model` — la classe de base de Flask-SQLAlchemy. En hériter suffit à
  déclarer une table.
- `__tablename__` — sans lui, SQLAlchemy invente un nom. On l'écrit toujours,
  au pluriel.
- `primary_key=True` — sur PostgreSQL, un entier en clé primaire devient
  automatiquement un `SERIAL` (auto-incrémenté).
- `nullable=False` — la contrainte NOT NULL, **dans la base**. C'est la seule
  garantie réelle: les validators du formulaire, eux, se contournent.
- `unique=True` + `index=True` — un index unique. Il sert deux choses:
  interdire les doublons, et accélérer les recherches sur cette colonne.
- `default=1` — valeur par défaut appliquée **par Python** à l'insertion.
  `server_default` serait appliquée par la base (visible aussi pour les lignes
  insérées à la main en SQL).
- `db.String(255)` vs `db.Text` — longueur maximale imposée ou texte libre.

## Le mixin BaseEntity

```python
class BaseEntity:                        # PAS db.Model: aucune table
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    deleted_at = db.Column(db.DateTime(timezone=True))
    active = db.Column(db.Boolean, nullable=False, default=True,
                       server_default=db.true())
```

Une classe *mixin* n'est pas un modèle: elle n'a pas de `__tablename__` et
SQLAlchemy recopie ses colonnes dans chaque modèle qui en hérite. Les six tables
du projet ont donc les mêmes colonnes techniques sans duplication de code.

- `server_default=func.now()` — c'est la base qui horodate à l'INSERT.
- `onupdate=func.now()` — SQLAlchemy met la valeur à jour à chaque UPDATE.
- `active` / `deleted_at` — le **soft delete**: on marque au lieu de supprimer.
  `UserService.delete()` appelle `soft_delete()`, et `find_all()` filtre sur
  `active=True`. Avantage: l'historique reste cohérent (les paniers d'un user
  supprimé existent encore). Inconvénient: il faut penser à filtrer partout, et
  un email « libéré » reste occupé par la contrainte unique.

L'ordre d'héritage `class Item(BaseEntity, db.Model)` est une convention: les
mixins d'abord, `db.Model` en dernier.

## Relations

### one-to-many

Un utilisateur a plusieurs paniers. **La clé étrangère est toujours du côté
« many »**:

```python
class Basket(BaseEntity, db.Model):
    user_id = db.Column(db.ForeignKey('users.user_id'))       # <- la FK ici
    user = db.relationship("User", back_populates="baskets")

class User(BaseEntity, db.Model):
    baskets = db.relationship('Basket', back_populates='user',
                              cascade='all, delete-orphan')
```

Deux choses différentes:

- `db.Column(db.ForeignKey(...))` = une **colonne** réelle, une contrainte dans
  la base;
- `db.relationship(...)` = un **attribut Python**, aucune colonne. C'est lui qui
  permet d'écrire `basket.user.username` ou de boucler sur `user.baskets`.

`back_populates` relie les deux attributs: `basket.user = u` ajoute
automatiquement `basket` dans `u.baskets`. Sans lui, les deux côtés peuvent se
désynchroniser en mémoire jusqu'au prochain rechargement.

Le nom de la classe cible est passé **en chaîne** (`"User"`): SQLAlchemy résout
les noms à la fin des imports, ce qui évite les imports circulaires entre
modèles.

### many-to-many avec données

Un utilisateur a plusieurs rôles, un rôle a plusieurs utilisateurs. Deux
solutions:

1. `db.Table` — une simple table de liaison, si elle ne contient que les deux FK;
2. **une entité**, dès qu'on veut y stocker autre chose.

Ici on veut savoir *quand* le rôle a été attribué (les colonnes de
`BaseEntity`), donc une entité:

```python
class UserRole(BaseEntity, db.Model):
    __tablename__ = "user_roles"
    role_id = db.Column(db.ForeignKey("roles.role_id"), primary_key=True)
    user_id = db.Column(db.ForeignKey("users.user_id"), primary_key=True)
    user = db.relationship('User', back_populates="roles")
    role = db.relationship('Role', back_populates="users")
```

La clé primaire **composée** (les deux colonnes `primary_key=True`) garantit
qu'une paire (user, role) n'existe qu'une fois. `BasketItem` suit exactement le
même schéma avec `quantity` en plus.

Conséquence pratique: `user.roles` contient des `UserRole`, pas des `Role`. Pour
avoir les noms, on traverse:

```python
def role_names(self):
    return [user_role.role.role_name for user_role in self.roles]
```

### Les cascades

```python
roles = db.relationship('UserRole', back_populates='user',
                        cascade='all, delete-orphan')
```

- `all` — les opérations (save, merge, refresh, delete…) se propagent aux
  enfants: `db.session.add(user)` insère aussi ses `UserRole` et ses paniers.
- `delete-orphan` — retirer un enfant de la collection le supprime en base.
  C'est ce qui fait fonctionner `Basket.remove_item()`:
  `self.items.remove(basket_item)` suffit, le DELETE part au `commit()`.

Sans cascade, supprimer un user avec des rôles échoue: la base refuse de laisser
des lignes `user_roles` pointant vers un user inexistant (violation de clé
étrangère).

`Item.basket_items` est déclaré dans le même esprit: supprimer un article le
retire des paniers où il se trouvait, au lieu de faire échouer la suppression.

## La logique métier dans le modèle

Un modèle n'est pas qu'un sac de colonnes. Tout ce qui ne concerne que l'entité
lui appartient:

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

Remarquez ce que la méthode **ne fait pas**: pas de `db.session`, pas de
`commit`. Le modèle manipule des objets, le service décide de la transaction.
Résultat: `BasketService.add_item()` et `BasketSeed` utilisent la même méthode
sans dupliquer la règle.

## Requêter

```python
Item.query.all()                                     # SELECT * FROM items
Item.query.filter_by(item_id=3).first()              # ... WHERE item_id = 3, ou None
Item.query.filter_by(active=True).order_by(Item.item_id).all()
Item.query.filter(Item.stock > 0).count()
Basket.query.filter_by(user_id=1, closed=False).first()
```

`.first()` renvoie `None` si rien ne correspond; `.one()` **lève une exception**
(`NoResultFound`). Le projet utilise systématiquement `.first()` + un test
`is None`: c'est plus facile à traiter proprement qu'un try/except.

## Le piège des N+1 requêtes

```python
for user in User.query.all():          # 1 requête
    print(user.role_names())           # + 1 requête par user pour charger ses rôles
```

100 utilisateurs = 101 requêtes. Sur une liste, on charge les relations d'un coup:

```python
from sqlalchemy.orm import joinedload

User.query.options(joinedload(User.roles)).all()      # 1 seule requête
```

La Debug Toolbar (onglet SQLAlchemy) affiche le nombre de requêtes par page:
c'est l'outil pour repérer ces cas. Le projet ne l'optimise pas — le volume de
données de démonstration ne le justifie pas — mais sachez le reconnaître.
