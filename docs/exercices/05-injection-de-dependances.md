# Exercices — Étape 05

Le sujet: le conteneur, les durées de vie, et ce que l'injection rend possible
(remplacer une implémentation sans toucher aux vues).

---

## 1. Rendre son propre service injectable

**Objectif** — appliquer le mécanisme à du code que vous avez écrit.

Reprenez le `CategoryService` de l'étape 04:

1. décorez-le avec `@injectable`;
2. supprimez toutes les constructions manuelles (`CategoryService()`) dans les
   controllers;
3. déclarez le service en paramètre annoté des vues, avec `@inject`.

Questions:

- combien de lignes avez-vous supprimées ? Combien ajoutées ?
- qu'avez-vous eu à modifier dans un éventuel fichier de configuration ?

**Critère de réussite** — `/categories` fonctionne, et `grep -rn "Service()" app/controllers/`
ne renvoie plus rien.

---

## 2. Observer les trois scopes

**Objectif** — voir la différence au lieu de la croire.

Ajoutez un compteur à un service:

```python
@injectable
class CompteurService:
    def __init__(self):
        self.appels = 0
        app.logger.debug(f"CompteurService construit: {id(self)}")

    def incrementer(self):
        self.appels += 1
        return self.appels
```

et une route de diagnostic:

```python
@app.get('/__probe')
@inject
def probe(compteur: CompteurService):
    return f"instance={id(compteur)} appels={compteur.incrementer()}"
```

Testez les trois scopes en rechargeant plusieurs fois la page:

| Scope | `instance` change ? | `appels` repart à 1 ? |
|---|---|---|
| `SINGLETON` | | |
| `SCOPED` | | |
| `TRANSIENT` | | |

Remplissez le tableau, puis supprimez la route.

**Critère de réussite** — vous pouvez expliquer ce que `flask.g` a à voir avec la
colonne du milieu.

---

## 3. Le bug que le mauvais scope provoque

**Objectif** — comprendre pourquoi `AuthService` sera `SCOPED` à l'étape 06.

Imaginez un service qui mémorise « l'utilisateur courant » (vous le construirez à
l'étape suivante). Simulez-le:

```python
@injectable      # SINGLETON par défaut: c'est le bug
class FauxAuthService:
    def __init__(self):
        self.utilisateur = None

    def connecter(self, nom):
        self.utilisateur = nom

    def courant(self):
        return self.utilisateur
```

Deux routes: `/__login/<nom>` qui appelle `connecter`, et `/__moi` qui affiche
`courant()`.

1. Ouvrez deux navigateurs différents (ou un navigateur + une fenêtre privée).
2. Connectez-vous comme « alice » dans le premier, puis appelez `/__moi` dans le
   second. Que voyez-vous ?
3. Passez le service en `Scope.SCOPED`. Refaites l'essai. Que se passe-t-il — et
   pourquoi l'information est-elle perdue entre deux requêtes ?
4. Conclusion: où faut-il stocker l'identité pour qu'elle survive à la requête
   **sans** fuiter entre utilisateurs ? (Réponse à l'étape 06.)

**Critère de réussite** — vous avez vu de vos yeux l'identité d'un utilisateur
apparaître dans la session d'un autre.

---

## 4. Substituer une implémentation (le vrai intérêt)

**Objectif** — utiliser l'injection pour tester sans base de données.

Écrivez un petit script `essai_double.py`:

```python
from app import app
from app.framework.injector import DependencyConfig, Injector, Scope
from app.services.item_service import ItemService


class FauxItemService(ItemService):
    def find_all(self):
        return []          # catalogue vide, sans toucher la base


Injector(app, config=lambda c: c.bind(
    DependencyConfig(ItemService, FauxItemService, Scope.SINGLETON)))

client = app.test_client()
print("Aucun article" in client.get('/items').get_data(as_text=True))
```

Questions:

- avez-vous modifié une seule ligne de `item_controller.py` ?
- comment feriez-vous la même chose **sans** injection de dépendances ?
- pourquoi le paramètre `config` de `Injector` existe-t-il, alors que
  `@injectable` suffit en production ?

**Critère de réussite** — le script imprime `True` sans qu'aucun article ne soit
en base.

---

## 5. Étendre le framework: `@transactional`

**Objectif** — écrire un décorateur utile, sur le modèle de ceux du projet.

Les services répètent tous le même bloc:

```python
try:
    db.session.commit()
except Exception as e:
    app.logger.error(...)
    db.session.rollback()
    return None
```

Écrivez `app/framework/decorators/transactional.py`:

```python
def transactional(func):
    """Commit à la sortie, rollback si une exception remonte."""
    ...
```

Consignes:

- la fonction décorée ne doit plus appeler `commit()` elle-même;
- en cas d'exception: `rollback()`, journalisation, et retour `None`;
- appliquez-le à deux méthodes de `ItemService` et vérifiez que le CRUD marche
  toujours.

Questions:

- que se passe-t-il si une méthode décorée en appelle une autre, elle aussi
  décorée ? (Cherchez « transaction imbriquée ».)
- pourquoi ne pas mettre ce décorateur sur **toutes** les méthodes, y compris les
  lectures ?

**Critère de réussite** — `ItemService.insert` et `update` ne contiennent plus de
`try/except/commit`, et les tests de l'étape 04 passent encore.

---

## 6. Une limite du conteneur maison

**Objectif** — connaître les limites de ce qu'on a écrit.

1. Créez deux services qui se demandent mutuellement dans leur `__init__`
   (A a besoin de B, B a besoin de A), et appelez une route qui utilise A.
2. Que se passe-t-il ? Lisez la fin du message d'erreur.
3. Où, dans `injector.py`, faudrait-il détecter le cycle ? Quelle information
   faudrait-il garder pendant la résolution ?
4. Implémentez la détection: le conteneur doit lever une erreur explicite
   (`"dépendance circulaire: A -> B -> A"`) au lieu de partir en récursion.

**Critère de réussite** — le cycle produit un message compréhensible, et les
dépendances normales continuent de fonctionner.
