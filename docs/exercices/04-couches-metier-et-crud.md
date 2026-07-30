# Exercices — Étape 04

Le sujet: faire circuler une donnée à travers les couches, valider les saisies, et
tenir une transaction.

---

## 1. Un CRUD complet, de bout en bout

**Objectif** — traverser les six couches une fois, en autonomie.

Faites pour `Category` (créée à l'étape 03) ce que le projet fait pour `Item`:

| Couche | Fichier à écrire |
|---|---|
| DTO | `app/dtos/category_dto.py` |
| Mapper | `app/mappers/category_mapper.py` |
| Formulaire | `app/forms/category/category_form.py` |
| Service | `app/services/category_service.py` |
| Controller | `app/controllers/category_controller.py` |
| Templates | `app/templates/categories/{list,details,add_or_update}.html` |

Consignes:

- cinq routes: liste, détail, ajout, édition, suppression;
- le service ne renvoie que des **DTO**;
- la suppression doit refuser de supprimer une catégorie qui contient des
  articles — et le dire à l'utilisateur (pas une erreur 500).

**Critère de réussite** — vous n'avez écrit `Category.query` que dans le service,
et `/categories` fonctionne sans qu'aucun template ne touche une entité.

<details><summary>Coup de pouce</summary>

Pour le refus de suppression: le service retourne `None`, le controller
transforme ça en `flash(..., "danger")`. Ou mieux: une méthode
`can_be_deleted()` sur le modèle.
</details>

---

## 2. Une recherche (formulaire en GET)

**Objectif** — comprendre pourquoi tout n'est pas en POST.

Ajoutez un champ de recherche sur `/items`: `GET /items?q=clavier` filtre le
catalogue par nom.

Consignes:

- lecture du paramètre avec `request.args.get('q', type=str)`;
- le filtrage se fait dans le **service**
  (`find_all(search=None)`), pas dans le controller ni le template;
- le champ conserve sa valeur après recherche;
- utilisez `ilike` pour être insensible à la casse.

Questions:

- pourquoi cette action est-elle en GET alors que « ajouter au panier » sera en
  POST ?
- que doit-il se passer si `q` contient `%` ou `_` ? Essayez.

**Critère de réussite** — l'URL est partageable (elle contient la recherche), et
`grep -n "query" app/controllers/` ne renvoie rien.

---

## 3. Un validator maison

**Objectif** — mettre une règle au bon endroit.

Règle métier: le nom d'un article ne doit pas contenir le mot « test »
(insensible à la casse).

1. Écrivez-la comme un validator WTForms réutilisable:

```python
def pas_de_mot_interdit(mot):
    def _validator(form, field):
        if mot.lower() in (field.data or '').lower():
            raise ValidationError(f"Le mot « {mot} » est interdit ici.")
    return _validator
```

2. Appliquez-le au champ `name` de `ItemForm`.
3. Vérifiez que le message s'affiche **sous le champ concerné**.

Puis répondez: cette règle aurait-elle pu aller dans le modèle ? Dans le service ?
Qu'est-ce qui change pour l'utilisateur, dans chaque cas ?

**Critère de réussite** — un POST avec « Clavier de test » réaffiche le formulaire
avec le message, sans rien écrire en base.

---

## 4. Une transaction qui couvre deux écritures

**Objectif** — comprendre que `commit()` marque la fin d'une **opération métier**.

Ajoutez à `ItemService` une méthode `insert_lot(forms)` qui insère plusieurs
articles **d'un seul coup**: soit tous, soit aucun.

1. Écrivez-la avec un seul `commit()` à la fin.
2. Testez avec trois formulaires dont le deuxième porte un nom déjà pris.
3. Combien d'articles en base après l'échec ? Est-ce le comportement voulu ?
4. Réécrivez-la avec un `commit()` par article: qu'observez-vous ?

**Critère de réussite** — vous pouvez expliquer, avec le résultat des deux
versions sous les yeux, pourquoi le `rollback()` est indispensable dans le
`except`.

---

## 5. La faille d'assignation de masse

**Objectif** — voir concrètement ce que protège le `isinstance` du mapper.

1. Remplacez le corps de `ItemMapper.form_to_entity` par une version
   « intelligente »:

```python
for name, value in form.data.items():
    if hasattr(item, name):
        setattr(item, name, value)
```

2. Ça marche ? Oui. Maintenant ajoutez à `ItemForm` un champ caché
   `<input type="hidden" name="active" value="false">` dans le template, et
   soumettez.
3. Que devient l'article ? Le formulaire déclarait-il ce champ ?
4. Imaginez la même chose sur un formulaire d'utilisateur avec un champ
   `password` ou `roles`.
5. Remettez la version d'origine.

**Critère de réussite** — vous savez expliquer en une phrase pourquoi le mapper
recopie les champs **un par un**, explicitement.

---

## 6. Le piège `DataRequired` / `InputRequired`

**Objectif** — connaître le piège avant de le rencontrer en production.

1. Remplacez `InputRequired()` par `DataRequired()` sur `ItemForm.stock`.
2. Créez un article avec un stock de `0`. Que dit le formulaire ?
3. Expliquez le lien avec la notion de valeur *falsy* en Python.
4. Cherchez, dans les formulaires du projet, tous les champs où ce piège pourrait
   se reproduire (indice: les nombres, et les booléens).
5. Remettez `InputRequired`.

**Critère de réussite** — vous savez énoncer la règle: `DataRequired` pour du
texte, `InputRequired` pour un nombre qui peut valoir 0.

---

## 7. Et si on supprimait les couches ?

**Objectif** — savoir défendre (ou critiquer) l'architecture.

Réécrivez `item_details` en une seule fonction, sans service, sans DTO, sans
mapper — comme à l'étape 03. Puis répondez par écrit, en trois ou quatre phrases
chacune:

- qu'a-t-on gagné ?
- qu'a-t-on perdu ? (pensez aux tests, à une future API JSON, au renommage d'une
  colonne)
- à partir de quelle taille de projet le découpage devient-il rentable, selon
  vous ?

Il n'y a pas de réponse unique: on attend un avis argumenté.
