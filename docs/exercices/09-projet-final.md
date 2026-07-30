# Exercices — Étape 09 (révision et bilan)

Le projet est terminé. Ces exercices ne sont pas des exercices d'apprentissage:
ce sont des **révisions transversales**, à faire sur le code complet.

> Le grand exercice final, lui, est ailleurs: c'est le projet d'équipe décrit dans
> [`docs/14-projet-equipe-helpdesk-framework-maison.md`](docs/14-projet-equipe-helpdesk-framework-maison.md).
> Les exercices ci-dessous servent à s'y préparer, ils ne le remplacent pas.
>
> Les exercices par thème (un jeu par étape) sont dans
> [`docs/13-exercices.md`](docs/13-exercices.md) et dans les fichiers
> `EXERCICES.md` de chaque étape.

---

## 1. Relire le code en une heure

**Objectif** — savoir se repérer dans un projet en couches sans l'avoir écrit.

Sans exécuter le projet, répondez par écrit, en citant fichier et ligne:

1. quand un visiteur ouvre `/basket`, quelles requêtes SQL sont émises, et par
   quel code ?
2. combien d'objets `UserService` existent pendant une requête ? Et
   `AuthServiceImpl` ? Qu'est-ce qui le décide ?
3. quel code garantit qu'un `POST /items/3/delete` envoyé depuis un autre site
   échoue ?
4. où est décidé le nombre d'articles affichés sur la page d'accueil ?
5. si on renomme la colonne `items.name` en `items.label`, quels fichiers faut-il
   modifier ? (Faites la liste **avant** de tester.)

**Critère de réussite** — vos réponses tiennent en une page et sont vérifiables.

---

## 2. La suite de tests qui manque

**Objectif** — le projet n'a aucun test automatisé. C'est le plus gros manque.

Mettez en place `pytest` et couvrez en priorité ce qui est **silencieux quand
c'est cassé**:

```python
# tests/conftest.py
import pytest
from app import app as flask_app, db

@pytest.fixture
def client():
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'   # en mémoire
    with flask_app.app_context():
        db.create_all()
        yield flask_app.test_client()
        db.drop_all()
```

À couvrir:

- un anonyme sur `/basket` est redirigé vers `/login`;
- un simple USER ne peut pas ouvrir `/users`;
- un simple USER ne peut pas éditer le profil d'un autre;
- poster `roles=<id ADMIN>` en tant que USER ne donne pas le rôle;
- un POST sans jeton CSRF est refusé (400);
- `/login?next=https://evil.example` ne redirige pas vers l'extérieur;
- deux `/seed` de suite ne créent pas de doublons;
- un lien de réinitialisation déjà utilisé ne fonctionne plus.

Question: pourquoi une base SQLite en mémoire pour les tests, alors que
l'application tourne sur PostgreSQL ? Quelles différences pourraient masquer un
bug ?

**Critère de réussite** — `pytest` est vert, et **chaque** test échoue si vous
retirez la protection qu'il vérifie (vérifiez-le, un par un).

---

## 3. Revue de sécurité

**Objectif** — savoir auditer, pas seulement écrire.

Reprenez la liste « Ce que le projet ne fait pas » de
[`docs/09-authentification.md`](docs/09-authentification.md) et, pour chaque
point:

- estimez la gravité (que peut faire un attaquant ?);
- estimez l'effort de correction;
- classez: à corriger avant toute mise en ligne / plus tard / acceptable ici.

Puis cherchez **trois** faiblesses qui ne sont pas dans la liste. Pistes: les
messages d'erreur, les journaux (que loggue-t-on exactement ?), le contenu de la
Debug Toolbar, ce qui se passe si `SECRET_KEY` reste la valeur par défaut.

**Critère de réussite** — un tableau d'audit avec au moins trois entrées de votre
cru, argumentées.

---

## 4. Faire vivre la documentation

**Objectif** — comprendre que la doc se périme plus vite que le code.

1. Choisissez une modification qui touche plusieurs couches (par exemple: rendre
   la description d'un article facultative).
2. Faites-la.
3. Trouvez **tous** les endroits de `docs/` qui deviennent faux. Corrigez-les.
4. Combien y en avait-il ? Comment feriez-vous pour que ce genre d'écart se voie
   automatiquement ? (Pistes: des extraits de code testés, `doctest`, ou de la
   documentation générée depuis les docstrings.)

**Critère de réussite** — la modification est faite, `docs/` est cohérent, et vous
avez une proposition concrète pour limiter la dérive.

---

## 5. Préparer le projet d'équipe

**Objectif** — arriver au projet final avec des réflexes, pas des recettes.

Sans regarder le code du projet, écrivez de mémoire les squelettes suivants (30
minutes, feuille blanche):

1. un modèle avec une relation one-to-many et une cascade;
2. une entité d'association avec clé primaire composée;
3. un service avec `find_all`, `insert` et le bloc `try/commit/rollback`;
4. un formulaire avec trois validators, dont un sur un nombre;
5. un controller avec `@auth_required` + `@inject` et le motif POST/Redirect/GET;
6. un seeder avec `order` et le test d'idempotence.

Comparez ensuite avec [`readme.md`](readme.md) (l'aide-mémoire) et notez ce que
vous avez oublié: c'est exactement ce qu'il faudra revérifier pendant le projet.

**Critère de réussite** — vous savez écrire les six squelettes sans copier-coller.

Vous êtes prêt pour
[`docs/14-projet-equipe-helpdesk-framework-maison.md`](docs/14-projet-equipe-helpdesk-framework-maison.md).
