# Aide-mémoire (squelettes à recopier)

Version condensée du guide. Les explications détaillées sont dans
[README.md](README.md) et le dossier [docs/](docs/).

---

## 1) Modèles

```python
from app import db
from app.models.base_entity import BaseEntity

class Role(BaseEntity, db.Model):
    __tablename__ = "roles"
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), nullable=False, unique=True, index=True)
```

### 1.1) one-to-many (un panier a plusieurs lignes)

```python
class Basket(BaseEntity, db.Model):
    __tablename__ = "baskets"
    basket_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.user_id'))          # le "many" porte la FK
    items = db.relationship("BasketItem", back_populates='basket',
                            cascade='all, delete-orphan')

class BasketItem(BaseEntity, db.Model):
    __tablename__ = "basket_items"
    basket_id = db.Column(db.ForeignKey('baskets.basket_id'), primary_key=True)
    item_id = db.Column(db.ForeignKey('items.item_id'), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    basket = db.relationship('Basket', back_populates='items')
```

### 1.2) many-to-many avec données (user <-> role)

Table d'association = une entité à part entière, clé primaire composée:

```python
class UserRole(BaseEntity, db.Model):
    __tablename__ = "user_roles"
    role_id = db.Column(db.ForeignKey("roles.role_id"), primary_key=True)
    user_id = db.Column(db.ForeignKey("users.user_id"), primary_key=True)
    user = db.relationship('User', back_populates="roles")
    role = db.relationship('Role', back_populates="users")
```

---

## 2) Formulaires

```python
class ItemForm(FlaskForm):
    # class Meta: csrf = False    -> uniquement pour une API sans navigateur
    name = StringField('Nom', validators=[DataRequired(), Length(min=2, max=255)])
    stock = IntegerField('Stock', validators=[InputRequired(), NumberRange(min=0)])
```

`DataRequired` refuse `0` (falsy) — utiliser `InputRequired` pour les nombres.

---

## 3) Mappers

Traduire `Form -> Entity` et `Entity -> DTO`: un seul endroit à corriger quand un
champ change de nom.

```python
class ItemMapper(AbstractMapper):
    @staticmethod
    def entity_to_dto(item: Item):
        return ItemDTO.build_from_entity(item)

    @staticmethod
    def form_to_entity(form, item: Item):
        if isinstance(form, ItemForm):
            item.name = form.name.data
        return item
```

---

## 4) Services

Les fonctions pour contacter la DB:

- `find_one(id)` — une entité par sa clé primaire
- `find_one_by(**kwargs)` — par n'importe quelle colonne
- `find_all()` — tout
- `insert(form)` / `update(id, form)` / `delete(id)`

Toujours le même motif d'écriture:

```python
try:
    db.session.add(entity)      # inutile pour un update: l'entité est déjà suivie
    db.session.commit()
except Exception as e:
    app.logger.error(e)
    db.session.rollback()       # sans ça, la session reste cassée
    return None
```

---

## 5) Controllers (MVC)

```python
@app.route('/items/add', methods=['GET', 'POST'])
@auth_required(level="ADMIN")
@inject
def item_add(item_service: ItemService):
    form = ItemForm()

    if form.validate_on_submit():               # POST + CSRF + validators
        item_service.insert(form)
        return redirect(url_for('item_list'))   # POST/Redirect/GET

    return render_template('items/add_or_update.html', form=form, item=None)
```

Ordre des décorateurs: `@app.route` en haut, puis `@auth_required`, puis
`@inject`, puis la fonction.

---

## 6) Dépendances entre couches

- les mappers dépendent des modèles, des DTOs et des forms
- les services dépendent des modèles et des mappers
- les controllers dépendent des services
- les templates ne reçoivent que des DTOs

---

## 7) Base de données

La connection string se met dans `.env` ou `.env.local`
(`DATABASE_URL=postgresql://app:1234@127.0.0.1:5435/app`).

```bash
./sqlAlchemy.sh -i                   # initialiser le dossier migrations (déjà fait)
./sqlAlchemy.sh -m nom_migration     # créer une migration (autogenerate)
./sqlAlchemy.sh -u                   # appliquer les migrations
```

Le fichier de migration généré peut (et doit parfois) être modifié à la main:
Alembic ne connaît pas les données existantes. Recette pour ajouter une colonne
NOT NULL sur une table déjà peuplée:

1. `add_column(..., nullable=True)`
2. `op.execute("UPDATE ... SET ...")`
3. `op.alter_column(..., nullable=False)`

---

## 8) Lancer le serveur

```bash
python main.py
```

Pour déboguer depuis l'IDE: créer une configuration qui lance `main.py`
(launch.json dans VSCode, "Python run configuration" dans PyCharm).

---

## 9) Seed

```python
class ItemSeed(Seedable):
    order = 30                      # 10 roles, 20 users, 30 items, 40 paniers

    def seed(self):
        if Item.query.filter_by(name=name).first() is None:
            db.session.add(Item(name=name, ...))
        db.session.commit()
```

Rien à déclarer ailleurs: le fichier dans `app/seed/` est découvert
automatiquement. Route `GET /seed`, disponible seulement si `DEBUG=True`.
