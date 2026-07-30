# Étape 07 — Panier et commande

Les tables `baskets` et `basket_items` existent depuis l'étape 03, et
`Basket.add_item()` aussi. Il ne manquait que la couche autour: un service, des
routes, des pages.

Cette étape est la plus « métier » de la formation: peu de mécanique nouvelle,
mais des règles à faire respecter au bon endroit — et une faille classique à
éviter.

---

## Démarrer

```bash
docker compose up -d db-example
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py
```

`/seed` remplit déjà le panier de `test`. Connectez-vous avec ce compte et ouvrez
**Panier**.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/services/basket_service.py` | panier courant, ajout, retrait, validation |
| `app/dtos/basket_dto.py`, `app/mappers/basket_mapper.py` | transport |
| `app/forms/basket/basket_add_item_form.py` | `item_id` + `quantity` |
| `app/controllers/basket_controller.py` | `/basket`, `/basket/add`, `/basket/remove/<id>`, `/basket/checkout`, `/baskets` |
| `app/templates/baskets/details.html`, `list.html` | mon panier, et la vue admin |
| `app/templates/items/_item_table.html` | le tableau accueille le formulaire « au panier » |
| `app/templates/layout/main_layout.html` | + les liens Panier / Paniers |

### 1. La règle de sécurité de toute l'étape

Aucune route ne reçoit de `basket_id`. Le panier est **toujours** retrouvé à
partir du `user_id` de la session:

```python
def current_basket_entity(self, user_id: int) -> Basket:
    basket = Basket.query.filter_by(user_id=user_id, closed=False).first()
    ...
```

Si on acceptait un `basket_id` posté par le navigateur, il suffirait de changer un
champ caché pour remplir le panier du voisin. Cette faille a un nom, **IDOR**
(*Insecure Direct Object Reference*), et c'est l'une des plus fréquentes.

Même logique pour l'article: le formulaire envoie un `item_id`, mais le service le
**recharge depuis la base** et borne la quantité au stock:

```python
item = Item.query.filter_by(item_id=form.item_id.data, active=True).first()

if item is None:
    return None

quantity = form.quantity.data
if not item.in_stock(quantity):
    quantity = item.stock
```

Le formulaire exprime une intention; le service vérifie ce qui est possible.

### 2. Le service ne lit pas la session

```python
def add_item(self, user_id: int, form: BasketAddItemForm): ...
```

et non `session.get('user_id')` à l'intérieur. Trois raisons: le service reste
utilisable hors requête HTTP (seed, script, tâche planifiée), il devient testable
sans simuler de session, et la responsabilité « qui est connecté » reste à
`AuthService`.

### 3. Une transaction = une opération métier

`checkout()` fait trois choses qui doivent réussir **ensemble**:

```python
try:
    for basket_item in basket.items:                  # 1. décrémenter les stocks
        basket_item.item.stock = max(0, basket_item.item.stock - basket_item.quantity)

    basket.closed = True                              # 2. fermer le panier

    new_basket = Basket()                             # 3. en ouvrir un nouveau
    new_basket.user_id = user_id
    db.session.add(new_basket)

    db.session.commit()                               # UN SEUL commit
except Exception as e:
    db.session.rollback()                             # tout ou rien
    return None
```

Un `commit()` par étape laisserait la base incohérente en cas d'échec au milieu
(stocks décrémentés mais panier non validé). Le `commit()` marque la fin d'une
**opération métier complète**, pas d'une écriture.

Valider un panier ne le supprime pas: il passe en `closed=True` et devient
l'historique. C'est ce que montre le bas de la page `/basket`.

### 4. Un template, deux usages

`items/_item_table.html` sert maintenant au catalogue **et** au panier:

```jinja
{% with items = basket.items, is_basket = true %}
    {% include "items/_item_table.html" %}
{% endwith %}
```

Ça fonctionne parce que `ItemDTO.build_from_entity()` sait se construire depuis un
`Item` (quantité = stock) comme depuis un `BasketItem` (quantité = quantité
commandée). C'est le bénéfice concret du DTO introduit à l'étape 04.

### 5. `request.referrer`

```python
return redirect(request.referrer or url_for('item_list'))
```

`/basket/add` est appelée depuis le catalogue **et** depuis le panier: on renvoie
l'utilisateur d'où il venait. L'en-tête peut être absent, d'où le `or` — ne jamais
supposer sa présence.

---

## Exercices

### 1. Tenter l'IDOR

- Sur `/items`, ouvrez les outils de développement et modifiez le champ caché
  `item_id` d'une ligne pour un identifiant inexistant (`9999`), puis soumettez.
  Que se passe-t-il ? Où est-ce arrêté ?
- Cherchez dans le code s'il existe **un seul** endroit où un identifiant de
  panier viendrait du client. (Il n'y en a pas: c'est le point de l'étape.)
- Ajoutez volontairement une route `/basket/<int:basket_id>/add` qui fait
  confiance au paramètre, puis videz le panier d'un autre compte. Supprimez-la
  ensuite: vous saurez pourquoi on ne fait pas ça.

### 2. Le stock

- Ajoutez au panier une quantité supérieure au stock: que vaut la ligne créée ?
- L'article « Webcam 1080p » a un stock de 0. Que donne l'ajout ? Est-ce
  satisfaisant pour l'utilisateur ?
- Faites en sorte que le service prévienne l'appelant qu'il a réduit la quantité.
  **Contrainte**: le service ne doit pas appeler `flash()` — il ne connaît pas
  HTTP. Que retourner pour que le controller s'en charge ?

### 3. La transaction

- Dans `checkout()`, ajoutez `raise Exception("boum")` juste avant
  `db.session.commit()`. Les stocks sont-ils décrémentés en base ? Le panier est-il
  fermé ? Pourquoi ?
- Déplacez le `raise` **après** le `commit()`. Même question. Conclusion ?

### 4. Concurrence

Entre l'ajout au panier et la validation, quelqu'un d'autre peut commander le
dernier exemplaire.

- Que fait l'application aujourd'hui ?
- Que **devrait**-elle faire ? Écrivez la vérification manquante dans
  `checkout()`.
- Allez plus loin: pourquoi `max(0, ...)` masque-t-il le problème plutôt que de
  le résoudre ?

### 5. Le prix (plus ambitieux)

Le panier ne connaît que des quantités. Ajoutez un prix:

1. `price` sur `Item` — utilisez `db.Numeric(10, 2)` et **pas** `db.Float`.
   Pourquoi ? (Cherchez « float binaire arrondi monétaire ».)
2. `unit_price` sur `BasketItem`, **copié au moment de l'ajout au panier**.
   Pourquoi ne pas simplement lire `item.price` en affichant l'historique ?
3. un total par panier, calculé dans le **DTO** (pas dans le template).

---

## Pour aller plus loin

- `../09-projet-final/docs/07-services.md` (transactions, IDOR)
- `../09-projet-final/docs/11-templates-jinja.md` (`include` vs `macro`)

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`08-mot-de-passe-oublie-mailpit`](../08-mot-de-passe-oublie-mailpit/) — envoyer
des mails en développement, et un lien de réinitialisation sûr.
