# Étape 04 — Couches métier et CRUD

Le controller de l'étape 03 faisait tout: requêter la base, et passer des entités
au template. On découpe.

Quatre notions arrivent d'un coup, parce qu'elles n'ont de sens qu'ensemble:
**DTO**, **mapper**, **service**, **formulaire**. À la fin de l'étape, le
catalogue a un CRUD complet.

---

## Démarrer

```bash
docker compose up -d db-example
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py
```

`/seed`, puis `/items`: la liste a maintenant des boutons **Nouvel article**,
**Éditer**, **Supprimer**.

> Rien n'est protégé: n'importe quel visiteur peut tout modifier. C'est le sujet
> de l'étape 06 — et une bonne occasion de constater qu'un CRUD sans contrôle
> d'accès n'est pas une application.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/dtos/abstract_dto.py`, `item_dto.py` | ce que reçoit le template |
| `app/mappers/abstract_mapper.py`, `item_mapper.py` | traduction Form → Entity → DTO |
| `app/services/base_service.py` | le contrat CRUD commun |
| `app/services/item_service.py` | la seule couche qui parle à `db.session` |
| `app/forms/item/item_form.py` | validation des saisies (WTForms) |
| `app/templates/macros/form_macros.html` | macros: champs de formulaire, bouton supprimer |
| `app/templates/items/_item_table.html`, `add_or_update.html` | le tableau réutilisable, le formulaire |
| `app/controllers/item_controller.py` | 5 routes, plus une seule requête SQL |
| `app/__init__.py` | + `CSRFProtect(app)` |

### 1. Le DTO: une photo figée

```python
class ItemDTO(AbstractDTO):
    def __init__(self):
        self.item_id = None
        self.name = None
        self.description = None
        self.quantity = None
        self.stock = None
```

Pourquoi ne pas donner l'entité au template ?

1. une entité est vivante: lire une relation déclenche une requête SQL, et lève
   `DetachedInstanceError` si la session est fermée;
2. une entité contient des champs à ne jamais exposer (le hash du mot de passe,
   dès l'étape 06);
3. le template ne doit pas connaître le schéma de la base.

Détail à noter: `ItemDTO.build_from_entity()` sait se construire depuis un `Item`
**ou** depuis un `BasketItem` (`quantity` = stock disponible, ou quantité
commandée). C'est ce qui permettra de réutiliser le même tableau HTML pour le
catalogue et pour le panier, à l'étape 07.

### 2. Le mapper: le seul endroit qui traduit

```
 Form   --form_to_entity-->   Entity   --entity_to_dto-->   DTO
```

```python
@staticmethod
def form_to_entity(form, item: Item) -> Item:
    if isinstance(form, ItemForm):
        item.name = form.name.data
        item.description = form.description.data
        item.stock = form.stock.data
    return item
```

Le `isinstance` est une fonctionnalité, pas une maladresse: **chaque branche ne
recopie que les champs de son formulaire**. C'est ce qui empêchera, à l'étape 06,
qu'un POST sur « modifier mon profil » change le mot de passe. Le contraire —
`for k, v in form.data.items(): setattr(entity, k, v)` — s'appelle une faille
d'assignation de masse.

### 3. Le service: transactions et logique

```python
try:
    db.session.add(item)      # inutile pour un update: l'entité est déjà suivie
    db.session.commit()
except Exception as e:
    app.logger.error(f"insert item: {e}")
    db.session.rollback()     # SANS ÇA, la session reste cassée
    return None
```

Trois choses à retenir:

- `add()` ne fait rien en base: il attache l'objet à la session. C'est `commit()`
  qui écrit et remplit `item.item_id`.
- Pour un **update**, pas de `add()`: modifier les attributs d'une entité issue
  d'une requête suffit (*dirty tracking*).
- Le `rollback()` n'est pas décoratif: sans lui, toutes les requêtes suivantes de
  la même requête HTTP échouent avec `PendingRollbackError`.

Le service renvoie des **DTO**; les méthodes qui rendent une entité sont
suffixées `_entity` et réservées aux appels internes.

### 4. Le formulaire: la validation, au seul endroit qui compte

```python
class ItemForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired(), Length(min=2, max=255)])
    description = TextAreaField('Description', validators=[DataRequired()])
    stock = IntegerField('Stock', validators=[InputRequired(), NumberRange(min=0)])
```

**`InputRequired` et pas `DataRequired` sur `stock`**: `DataRequired` teste la
valeur comme un booléen, et `0` est falsy en Python — un stock à zéro serait
refusé.

Les attributs HTML (`required`) sont du confort: n'importe qui peut poster sans
passer par le formulaire. Les validators sont la seule vraie barrière, et la base
(`nullable=False`, `unique`) le dernier filet.

### 5. Le motif POST / Redirect / GET

```python
@app.route('/items/add', methods=['GET', 'POST'])
def item_add():
    form = ItemForm()

    if form.validate_on_submit():          # POST + CSRF + validators
        item = item_service.insert(form)
        ...
        return redirect(url_for('item_list'))     # <- redirection

    return render_template('items/add_or_update.html', form=form, item=None)
```

Après un POST réussi on **redirige**, sinon un F5 renvoie le formulaire (double
article, double commande). En cas d'échec au contraire, on rend le même
template: les saisies et les messages d'erreur sont conservés.

Et `flash()` est le seul moyen de faire passer un message à travers une
redirection.

### 6. CSRF

`CSRFProtect(app)` étend la vérification à **toutes** les requêtes
POST/PUT/DELETE, y compris nos boutons « supprimer » qui n'ont pas de formulaire
WTForms. Côté template: `{{ form.hidden_tag() }}`, ou
`{{ csrf_token() }}` pour un formulaire écrit à la main.

**Oublier `form.hidden_tag()` est l'erreur nº 1**: le formulaire « ne fait rien »,
`validate_on_submit()` renvoie toujours `False`.

### 7. Ce qui reste bancal

```python
item_service = ItemService()      # en haut de item_controller.py
```

Le controller choisit lui-même l'implémentation. Impossible de la remplacer par
un double dans un test, et chaque nouveau service ajoute une ligne de plomberie.
C'est l'étape 05.

---

## Exercices

### 1. Suivre le chemin d'une donnée

Ajoutez un champ `reference` (chaîne, unique) aux articles, de bout en bout:

modèle → migration → DTO → mapper → formulaire → templates.

Combien de fichiers ? Notez-les: c'est la « largeur » d'un changement dans une
architecture en couches — le prix à payer pour le découplage.

### 2. Casser volontairement les couches

- Dans `items/list.html`, essayez d'afficher `{{ item.basket_items }}`.
  Que se passe-t-il, et pourquoi ? (`item` est un DTO, pas une entité.)
- Dans `item_controller.py`, remplacez `item_service.find_all()` par
  `Item.query.all()`. La page marche-t-elle encore ? Qu'avez-vous perdu ?

### 3. Le piège `DataRequired`

Remplacez `InputRequired()` par `DataRequired()` sur `stock`, puis créez un
article avec un stock de `0`. Lisez le message d'erreur. Remettez
`InputRequired`.

### 4. Erreurs de validation

Soumettez le formulaire avec un nom d'une seule lettre et un stock négatif.

- Où s'affichent les messages ? Qui les génère ?
- Retirez `{{ form.hidden_tag() }}` de `add_or_update.html` et réessayez:
  décrivez précisément le symptôme. C'est celui que vous rencontrerez en vrai.

### 5. Un service complet

Écrivez `CategoryService` (si vous avez fait l'exercice `Category` de l'étape 03)
avec `find_all`, `find_one`, `insert`, `update`, `delete`, plus
`CategoryDTO`/`CategoryMapper` et un `CategoryForm`. Ajoutez un
`SelectField('Catégorie', coerce=int)` à `ItemForm`, dont les `choices` sont
remplies dans `__init__` depuis la base.

Question: pourquoi remplir `choices` depuis la base plutôt qu'en dur ? (Indice:
WTForms refuse toute valeur absente de `choices`.)

---

## Pour aller plus loin

- `../09-projet-final/docs/05-dtos-et-mappers.md`
- `../09-projet-final/docs/06-formulaires.md`
- `../09-projet-final/docs/07-services.md`

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`05-injection-de-dependances`](../05-injection-de-dependances/) — ne plus
construire les services dans les controllers, mais les déclarer.
