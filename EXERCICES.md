# Exercices — Étape 01

Chaque exercice précise **ce qu'on attend**, un **critère de réussite** vérifiable,
et un **coup de pouce** à lire seulement si vous bloquez.

Travaillez dans ce dossier, il est à vous. L'étape 02 contient une solution
possible pour ce qui touche au seeding; pour le reste, il y a plusieurs bonnes
réponses.

---

## 1. Une page de plus (routes, templates, héritage)

**Objectif** — maîtriser le trio route / template / `url_for`.

Ajoutez une page « À propos » qui affiche le nom de l'application, la version de
Flask utilisée et le nombre d'utilisateurs en base.

Consignes:

- route `GET /a-propos`, vue nommée `about`, dans `test_controller.py`;
- template `app/templates/home/about.html` qui **étend** `layout/main_layout.html`;
- un lien vers la page dans la barre de navigation, avec `url_for`;
- le nombre d'utilisateurs vient de `User.query.count()`.

**Critère de réussite** — vous pouvez renommer l'URL en `/about` sans toucher au
template.

<details><summary>Coup de pouce</summary>

`from flask import __version__` n'existe plus en Flask 3: utilisez
`importlib.metadata.version("flask")`.
</details>

---

## 2. Jinja: boucles, conditions, filtres

**Objectif** — savoir lire et écrire un template sans mettre de logique dedans.

Sur la page d'accueil, affichez les 10 `LiItem` sous forme de tableau avec:

- un numéro de ligne (1, 2, 3…) qui ne vient **pas** de `caption`;
- la valeur, et une colonne « pair / impair »;
- les valeurs supérieures à 500 en gras;
- sous le tableau: « moyenne: X » arrondie à 1 décimale.

**Critère de réussite** — aucune boucle `for` ni calcul dans le controller pour
l'affichage, et aucun calcul de moyenne dans le template au-delà d'un filtre.

<details><summary>Coup de pouce</summary>

`loop.index`, `{% if %}`, et les filtres `sum`, `length`, `round`. Pour la
moyenne: `{{ (items | sum(attribute='caption') / items | length) | round(1) }}`.
</details>

---

## 3. Un modèle, une migration, et la marche arrière

**Objectif** — faire un aller-retour complet avec Alembic sans perdre de données.

1. Créez `app/models/tag.py`: `Tag` avec `tag_id` et `label` (unique, indexé).
2. `./sqlAlchemy.sh -m "ajout tags"`.
3. **Lisez** le fichier généré. Repérez `upgrade()` et `downgrade()`.
4. `./sqlAlchemy.sh -u`, vérifiez la table dans PostgreSQL
   (`docker compose exec db-example psql -U app -d app -c '\d tags'`).
5. `flask db downgrade`, vérifiez que la table a disparu.
6. `flask db upgrade` à nouveau.

**Critère de réussite** — `flask db check` répond « No new upgrade operations
detected » à la fin.

<details><summary>Coup de pouce</summary>

`export FLASK_APP=app` avant les commandes `flask` (ou utilisez `sqlAlchemy.sh`,
qui le fait).
</details>

---

## 4. Lire le SQL avant de l'exécuter

**Objectif** — ne jamais appliquer une migration à l'aveugle.

Lancez `flask db upgrade --sql` (mode « offline »): Alembic imprime le SQL au
lieu de l'exécuter.

Questions, à répondre par écrit:

- quelles instructions sont générées pour la migration initiale ?
- où est stockée la révision courante ?
- que se passerait-il si deux développeurs créaient chacun une migration à
  partir de la même révision parente ?

**Critère de réussite** — vous savez expliquer le rôle de `down_revision`.

---

## 5. Diagnostiquer une panne d'auto-découverte

**Objectif** — comprendre que « le code existe » ne veut pas dire « il est
importé ».

Faites chacune de ces manipulations, notez le symptôme **exact**, puis annulez:

1. renommez `test_controller.py` en `test_controller.txt` → que donne `/` ?
2. remettez le `.py`, puis supprimez `from app.controllers import *` de
   `app/__init__.py` → même question;
3. supprimez `from app.models import *`, puis lancez
   `./sqlAlchemy.sh -m "essai"` → que contient la migration générée ?
   (supprimez-la ensuite);
4. dans `app/models/__init__.py`, remplacez `f.name[:-3]` par `f.name` → lisez
   l'erreur d'import et expliquez-la.

**Critère de réussite** — pour chaque cas, vous savez dire *quel* mécanisme a
échoué et *pourquoi le message d'erreur ressemble à ça*.

---

## 6. La liste de seeders tenue à la main

**Objectif** — mesurer le coût d'un enregistrement manuel (c'est le sujet de
l'étape 02).

Ajoutez un seeder `TagSeed` qui insère trois tags (le modèle `Tag` de
l'exercice 3), et faites-le exécuter par `/seed`.

Puis répondez:

- combien de fichiers avez-vous modifiés ?
- qu'arrive-t-il si vous oubliez la ligne dans `app/seed/__init__.py` ?
  Y a-t-il un message d'erreur, ou juste… rien ?
- comment feriez-vous pour qu'un fichier déposé dans `app/seed/` soit exécuté
  sans autre déclaration ? Écrivez votre idée en trois lignes avant de regarder
  l'étape 02.

**Critère de réussite** — `/seed` liste vos tags, et vous avez une hypothèse
écrite sur l'automatisation.
