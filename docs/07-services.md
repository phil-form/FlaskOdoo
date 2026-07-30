# 07 — Services

Fichiers: `app/services/`

## Le rôle du service

C'est **la seule couche qui parle à `db.session`**. Elle contient la logique
métier qui dépasse une entité seule, et elle décide des transactions.

Conséquences pratiques:

- un controller sans requête SQL est court, lisible et testable;
- la même logique sert aux pages, aux seeds, à une commande CLI, à une API;
- `grep -r "db.session" app/controllers/` doit ne rien renvoyer.

## Le contrat CRUD

`BaseService` (abstrait) impose six méthodes:

```python
find_all()              # tous les enregistrements, en DTO
find_one(entity_id)     # un, par clé primaire, ou None
find_one_by(**kwargs)   # un, par n'importe quelle colonne
insert(data)            # créer depuis un formulaire validé
update(entity_id, data) # modifier
delete(entity_id)       # supprimer
```

`ItemService` est l'implémentation de référence: si vous ajoutez une entité,
copiez-le.

**Convention de retour**: un service renvoie des **DTO**. Les méthodes qui
renvoient une entité sont suffixées `_entity` (`find_one_entity`,
`find_all_entities`) et réservées aux appels internes — par exemple
`UserService.insert()` a besoin de l'entité `Role` pour appeler
`user.add_role(role)`.

Toutes les méthodes du contrat ne sont pas toujours pertinentes. `RoleService`
n'autorise que la lecture, mais doit quand même déclarer les autres (sinon la
classe reste abstraite et Python refuse de l'instancier). D'où:

```python
def insert(self, data):
    raise NotImplementedError("Les rôles sont gérés par les seeds/migrations")
```

Une intention explicite, plutôt qu'un `pass` silencieux qui laisserait croire que
l'opération a réussi.

## La session SQLAlchemy

La session est un « cahier de brouillon »: elle accumule les changements et les
envoie à la base au `commit()`.

```python
db.session.add(item)      # attache un NOUVEL objet à la session (aucun SQL encore)
db.session.delete(item)   # marque pour suppression
db.session.commit()       # envoie tout (INSERT/UPDATE/DELETE) + valide la transaction
db.session.rollback()     # annule tout ce qui n'est pas commité
db.session.flush()        # envoie le SQL sans valider (pour obtenir un id)
```

Trois points qui surprennent souvent:

**1. Pas besoin de `add()` pour un update.** Une entité issue d'une requête est
déjà suivie par la session (*dirty tracking*): modifier ses attributs suffit,
`commit()` génère l'UPDATE.

```python
item = self.find_one_entity(entity_id)
ItemMapper.form_to_entity(form, item)      # on modifie l'objet
db.session.commit()                        # -> UPDATE items SET ...
```

**2. `commit()` remplit les clés primaires.** Après `db.session.add(item)`,
`item.item_id` est `None`; après `commit()` (ou `flush()`), il a la valeur
attribuée par la base.

**3. Flask-SQLAlchemy gère une session par requête HTTP** et la ferme à la fin.
C'est ce qui rend les entités inutilisables dans un template rendu plus tard —
et pourquoi on passe des DTO.

## Toujours try / commit / rollback

```python
try:
    db.session.add(item)
    db.session.commit()
except Exception as e:
    app.logger.error(f"insert item: {e}")
    db.session.rollback()
    return None
```

Le `rollback()` n'est pas décoratif: **sans lui, la session reste dans un état
d'erreur** et toutes les requêtes suivantes de la même requête HTTP échouent avec
`PendingRollbackError`. Un oubli se traduit par une page qui plante « sans
raison » après une erreur pourtant rattrapée.

Ce que le service fait de l'exception: il la **logue** (`app.logger.error`) et
renvoie `None`. Le controller traduit ce `None` en message utilisateur. Ne jamais
afficher le message de l'exception à l'utilisateur: il révèle des noms de
tables, de contraintes, parfois des données.

## Transactions: un commit = une opération métier

`BasketService.checkout()` fait trois choses qui doivent réussir **ensemble**:

```python
try:
    for basket_item in basket.items:                       # 1. décrémenter les stocks
        basket_item.item.stock = max(0, basket_item.item.stock - basket_item.quantity)

    basket.closed = True                                   # 2. fermer le panier

    new_basket = Basket()                                  # 3. en ouvrir un nouveau
    new_basket.user_id = user_id
    db.session.add(new_basket)

    db.session.commit()                                    # UN SEUL commit
except Exception as e:
    db.session.rollback()                                  # tout ou rien
    return None
```

Un `commit()` par étape laisserait la base dans un état incohérent en cas
d'échec au milieu (stocks décrémentés mais panier non validé). La règle: le
`commit()` marque la fin d'une **opération métier complète**, pas d'une écriture.

## Ne pas lire la session HTTP depuis un service

Le projet passe `user_id` en paramètre:

```python
def add_item(self, user_id: int, form: BasketAddItemForm): ...
```

plutôt que d'y accéder directement:

```python
def add_item(self, form):
    user_id = session.get('user_id')          # ← à éviter
```

Trois raisons: le service reste utilisable hors requête HTTP (seed, script,
tâche planifiée), il devient testable sans simuler une session, et la
responsabilité « qui est connecté » reste au seul endroit prévu pour ça
(`AuthService`).

## Sécurité: ne jamais faire confiance à un identifiant reçu

```python
def current_basket_entity(self, user_id: int) -> Basket:
    basket = Basket.query.filter_by(user_id=user_id, closed=False).first()
```

Le panier est retrouvé à partir du `user_id` **de la session**, jamais d'un
`basket_id` envoyé par le navigateur. Sinon il suffirait de modifier un champ
caché pour agir sur le panier de quelqu'un d'autre. Cette faille porte un nom:
*IDOR* (Insecure Direct Object Reference), et c'est l'une des plus fréquentes.

Même logique pour `add_item`: l'article est **rechargé depuis la base**
(`Item.query.filter_by(item_id=form.item_id.data, active=True).first()`) et la
quantité est bornée par le stock. Le formulaire indique une intention; le service
vérifie ce qui est possible.

## Un service qui a un état: AuthService

Presque tous les services sont **sans état** (aucune donnée conservée entre deux
appels), donc partageables — d'où `Scope.SINGLETON` dans l'injecteur.

`AuthServiceImpl`, lui, garde l'utilisateur courant en mémoire pour ne pas le
recharger à chaque appel. Il est donc enregistré en `Scope.SCOPED`: **une
instance par requête HTTP**. En singleton, l'utilisateur A finirait par voir
l'identité de B — un bug de sécurité classique et difficile à reproduire.

Détail d'implémentation à noter, le chargement paresseux:

```python
def get_current_user(self):
    if not self.__loaded:              # une seule requête SQL par requête HTTP,
        self.__loaded = True           # et zéro sur une page publique
        ...
```

Voir [08-injection-de-dependances.md](08-injection-de-dependances.md) pour les
scopes et [09-authentification.md](09-authentification.md) pour la suite.
