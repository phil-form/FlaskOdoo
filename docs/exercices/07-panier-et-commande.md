# Exercices — Étape 07

Le sujet: des règles métier, une transaction qui doit tenir, et un identifiant
qu'on ne doit jamais croire.

---

## 1. Tenter l'IDOR

**Objectif** — vérifier que le panier d'un utilisateur est inatteignable depuis
l'extérieur.

1. Connecté en `test`, sur `/items`, modifiez avec les outils de développement le
   champ caché `item_id` d'une ligne pour un identifiant inexistant (`9999`), puis
   soumettez. Que se passe-t-il ? Où est-ce arrêté ?
2. Cherchez dans tout le projet un endroit où un `basket_id` viendrait du client:
   `grep -rn "basket_id" app/controllers/ app/forms/`. Que constatez-vous ?
3. Ajoutez **volontairement** la faille:

```python
@app.post('/basket/<int:basket_id>/add')
@auth_required()
@inject
def basket_add_item_vulnerable(basket_id, basket_service: BasketService):
    basket = Basket.query.filter_by(basket_id=basket_id).first()
    ...
```

Depuis le compte `test`, ajoutez un article dans le panier d'`admin`.
Puis **supprimez cette route**.

4. Écrivez la règle en une phrase, celle que le projet applique partout.

**Critère de réussite** — vous avez réussi à polluer le panier d'un autre compte
avec la version vulnérable, et vous savez pourquoi la version normale l'empêche.

---

## 2. Le stock, et ce que voit l'utilisateur

**Objectif** — distinguer « la règle est appliquée » de « la règle est comprise ».

1. Ajoutez au panier une quantité supérieure au stock. Que vaut la ligne créée ?
   L'utilisateur en est-il informé ?
2. L'article « Webcam 1080p » a un stock de 0: que donne l'ajout ? Est-ce
   acceptable pour une boutique ?
3. Modifiez le service pour qu'il signale à l'appelant que la quantité a été
   réduite. **Contrainte**: `BasketService` ne doit pas appeler `flash()` — il ne
   connaît pas HTTP.
   Proposez deux conceptions (par exemple un retour enrichi, ou une exception
   métier) et implémentez celle que vous préférez.
4. Faites refuser complètement l'ajout d'un article en rupture, avec un message
   clair.

**Critère de réussite** — l'utilisateur qui demande 50 exemplaires d'un article à
12 en stock voit un message qui le dit, et le panier contient 12.

---

## 3. Quantité zéro

**Objectif** — une petite règle, mais où la mettre ?

Aujourd'hui `BasketAddItemForm` impose `NumberRange(min=1)`. On veut que saisir
`0` dans le panier **retire** la ligne.

1. Modifiez la validation pour accepter `0`.
2. Implémentez le comportement. Où: formulaire, controller, service, ou modèle ?
   Justifiez.
3. Vérifiez qu'un `0` sur le catalogue (et non dans le panier) ne crée pas une
   ligne vide.

**Critère de réussite** — mettre 0 puis valider retire l'article, et le panier ne
contient jamais de ligne à quantité nulle.

---

## 4. La transaction du checkout

**Objectif** — voir de ses yeux ce que garantit un `commit()` unique.

1. Dans `BasketService.checkout()`, insérez `raise Exception("boum")` **juste
   avant** `db.session.commit()`. Validez un panier.
   - les stocks sont-ils décrémentés en base ?
   - le panier est-il fermé ?
   - un nouveau panier a-t-il été créé ?
2. Déplacez le `raise` **juste après** le `commit()`. Mêmes questions.
3. Retirez le `raise`, puis remplacez le `commit()` unique par un `commit()` après
   chaque étape. Refaites l'essai du point 1: qu'est-ce qui change ?
4. Remettez le code d'origine et écrivez la conclusion en une phrase.

**Critère de réussite** — vous pouvez expliquer, résultats en main, pourquoi
« un commit = une opération métier ».

---

## 5. La concurrence

**Objectif** — repérer une faille de logique que les tests classiques ne voient
pas.

Scénario: deux clients ajoutent le dernier exemplaire d'un article à leur panier,
puis valident tous les deux.

1. Reproduisez-le (deux navigateurs, ou deux `test_client`).
2. Que vaut le stock à la fin ? Est-ce cohérent ?
3. Pourquoi `max(0, ...)` dans `checkout()` **masque**-t-il le problème plutôt que
   de le résoudre ?
4. Ajoutez la vérification manquante: au moment du checkout, si le stock ne suffit
   plus, refuser et prévenir l'utilisateur.
5. Question ouverte: même avec cette vérification, deux checkouts simultanés
   peuvent-ils encore se croiser ? Cherchez `SELECT ... FOR UPDATE` et
   `with_for_update()`.

**Critère de réussite** — le deuxième client reçoit un refus explicite, et le stock
ne devient jamais négatif.

---

## 6. Le prix (le plus long)

**Objectif** — ajouter une donnée qui a des pièges connus.

1. `price` sur `Item`: utilisez `db.Numeric(10, 2)` et **pas** `db.Float`.
   Écrivez pourquoi (cherchez « float binaire arrondi monétaire », et essayez
   `0.1 + 0.2` en Python).
2. `unit_price` sur `BasketItem`, **copié au moment de l'ajout au panier**.
   Pourquoi ne pas simplement lire `item.price` en affichant une commande passée ?
3. Total par ligne et total du panier, calculés dans le **DTO** (pas dans le
   template, pas dans le controller).
4. Affichez les montants avec deux décimales et le symbole €. Utilisez un filtre
   Jinja maison (`app.template_filter`).

**Critère de réussite** — après un changement de prix d'un article, une commande
déjà validée affiche toujours l'ancien montant.

---

## 7. Un tableau de bord (agrégation)

**Objectif** — écrire une requête qui n'est pas un simple `find_all`.

Ajoutez une page admin `/baskets/stats` qui affiche, pour chaque article: la
quantité totale commandée (paniers validés uniquement), et le nombre de commandes
concernées.

Consignes:

- la requête d'agrégation va dans un **service**;
- utilisez `db.session.query(...).join(...).group_by(...)` avec `func.sum` et
  `func.count`;
- le template reçoit une liste de DTO (ou de simples dictionnaires), pas des
  tuples SQLAlchemy bruts;
- réservé aux ADMIN.

**Critère de réussite** — les totaux correspondent à ce que vous voyez dans
`/baskets`, et la page fait **une** requête SQL, pas une par article.
