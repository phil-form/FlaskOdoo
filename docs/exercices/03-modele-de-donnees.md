# Exercices — Étape 03

Le sujet: les relations, les cascades, le soft delete, et les migrations sur une
base qui contient déjà des données.

---

## 1. one-to-many: les catégories

**Objectif** — écrire une relation dans le bon sens.

Un article appartient à une catégorie; une catégorie contient plusieurs articles.

1. `app/models/category.py`: `category_id`, `name` (unique, indexé), et la
   collection `items`;
2. dans `Item`: la **clé étrangère** et la relation inverse;
3. migration, relecture, application;
4. `app/seed/category_seed.py` avec `order = 25`, et rattachez chaque article de
   `ItemSeed` à une catégorie;
5. affichez la catégorie dans la colonne « Nom » de `/items`
   (`{{ item.category.name }}` — ça marche ici parce que le template reçoit des
   entités… on en reparle à l'étape 04).

**Critère de réussite** — `/seed` liste 5 seeders dans le bon ordre,
`flask db check` ne détecte aucun écart, et `/items` affiche les catégories.

<details><summary>Coup de pouce</summary>

La clé étrangère est **toujours** du côté « many »: `Item.category_id`. La
relation `Category.items` n'ajoute aucune colonne à `categories`.
</details>

---

## 2. many-to-many: deux façons de faire

**Objectif** — savoir choisir entre `db.Table` et une entité d'association.

Ajoutez des **tags** aux articles (un article a plusieurs tags, un tag concerne
plusieurs articles).

1. Première version avec une simple table de liaison:

```python
item_tags = db.Table(
    'item_tags',
    db.Column('item_id', db.ForeignKey('items.item_id'), primary_key=True),
    db.Column('tag_id', db.ForeignKey('tags.tag_id'), primary_key=True),
)
```
et `tags = db.relationship('Tag', secondary=item_tags, back_populates='items')`.

2. Puis répondez: où mettriez-vous la **date** d'ajout d'un tag à un article ?
   Et qui l'a ajouté ?

3. Deuxième version: transformez la liaison en entité `ItemTag(BaseEntity,
   db.Model)`. Qu'est-ce qui change dans le code qui parcourt les tags ?

**Critère de réussite** — vous savez énoncer la règle: « dès qu'une table de
liaison porte une donnée, c'est une entité ». C'est exactement pourquoi `UserRole`
et `BasketItem` sont des classes dans ce projet.

---

## 3. Les cascades, en cassant tout

**Objectif** — comprendre ce que fait `cascade='all, delete-orphan'`.

Dans un shell (`python`, puis `from app import app, db`):

```python
with app.app_context():
    from app.models.user import User
    u = User.query.filter_by(username='test').first()
    db.session.delete(u)
    db.session.commit()
```

1. Ses lignes `user_roles` et ses paniers existent-ils encore ?
   (`select * from user_roles;` en SQL.)
2. Retirez `cascade='all, delete-orphan'` de `User.roles`, relancez `/seed` sur
   une base neuve, refaites la suppression: lisez l'erreur PostgreSQL et
   traduisez-la en français.
3. Remettez la cascade. Puis testez `basket.items.remove(ligne)` suivi d'un
   `commit()`: la ligne disparaît-elle de la base ? Quelle partie de la cascade
   est responsable ?

**Critère de réussite** — vous savez dire ce que fait `all` et ce que fait
`delete-orphan`, séparément.

---

## 4. Soft delete: les conséquences

**Objectif** — voir qu'une bonne idée a un prix.

1. Ajoutez `POST /items/<id>/desactiver` qui appelle `item.soft_delete()` puis
   commit (le controller peut encore parler à la base à cette étape).
2. L'article disparaît-il de `/items` ? Pourquoi ? Et de `/items/<id>` ?
3. Essayez de créer un nouvel article avec le **même nom** que l'article
   désactivé. Que dit la base ? Est-ce le comportement souhaitable pour une
   boutique ?
4. Proposez deux solutions (au moins une qui touche au modèle, une qui n'y touche
   pas).

**Critère de réussite** — vous pouvez expliquer pourquoi le soft delete oblige à
filtrer `active=True` **partout**, et ce qu'on oublie toujours de filtrer.

---

## 5. Le problème N+1, mesuré

**Objectif** — savoir repérer et corriger le piège de performance classique d'un
ORM.

1. Activez l'écho SQL: `app.config['SQLALCHEMY_ECHO'] = True` (ou l'onglet
   SQLAlchemy de la Debug Toolbar).
2. Comptez les requêtes déclenchées par:

```python
with app.app_context():
    from app.models.user import User
    for u in User.query.all():
        print(u.role_names())
```

3. Corrigez avec `joinedload`:

```python
from sqlalchemy.orm import joinedload
User.query.options(joinedload(User.roles)).all()
```

4. Combien de requêtes maintenant ? Que devient le SQL généré ?
5. Faites le même exercice sur `/items` après avoir ajouté les catégories
   (exercice 1).

**Critère de réussite** — vous savez donner la formule « 1 + N » et montrer les
deux versions du SQL.

---

## 6. Une migration sur une base peuplée

**Objectif** — refaire, en conscience, ce que la migration
`2b86203c0955` fait pour `email`.

1. Assurez-vous d'avoir des articles en base (`/seed`).
2. Ajoutez à `Item` une colonne `reference` (chaîne, **unique**, **non nulle**).
3. Générez la migration, appliquez-la telle quelle: elle doit **échouer**.
   Lisez l'erreur.
4. Corrigez le fichier avec la recette en trois temps:
   - ajout en `nullable=True`,
   - `op.execute("UPDATE items SET reference = 'REF-' || item_id WHERE reference IS NULL")`,
   - passage en `nullable=False`.
5. `flask db downgrade` puis `flask db upgrade` pour vérifier les deux sens.

**Critère de réussite** — la migration s'applique sur une base pleine **et** sur
une base vide, et `flask db check` est propre.
