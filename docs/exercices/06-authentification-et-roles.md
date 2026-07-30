# Exercices — Étape 06

Le sujet: mots de passe, session, rôles — et surtout les erreurs qui coûtent cher.
Plusieurs exercices consistent à **attaquer** l'application: c'est la seule façon
de vérifier qu'elle tient.

---

## 1. La matrice des droits

**Objectif** — savoir ce que l'application autorise, sans le deviner.

Remplissez ce tableau **en testant** (anonyme, `test`, `admin`). Notez le code
HTTP obtenu ou la page d'arrivée.

| Route | anonyme | USER | ADMIN |
|---|---|---|---|
| `GET /items` | | | |
| `GET /items/add` | | | |
| `POST /items/1/delete` | | | |
| `GET /users` | | | |
| `GET /users/1` | | | |
| `GET /users/1/edit` (profil d'un autre) | | | |
| `GET /users/2/edit` (son propre profil) | | | |
| `POST /users/1/delete` | | | |

Puis: y a-t-il une case qui vous surprend ? Une qui vous paraît trop permissive ?

**Critère de réussite** — le tableau est rempli par des essais, pas par lecture du
code, et vous savez dire quel décorateur produit chaque refus.

---

## 2. Les garde-fous du décorateur

**Objectif** — comprendre une API conçue pour empêcher l'erreur, et savoir en
écrire une.

Le décorateur refuse deux configurations **au démarrage**. Vérifiez-le:

1. Dans `user_controller.py`, remplacez `@auth_required(or_is_current_user=True)`
   par `@auth_required(level="USER", or_is_current_user=True)` et relancez.
   Que se passe-t-il, et **quand** ?
2. Même question en retirant le paramètre `user_id` de la signature de la vue.
3. Lisez le message d'erreur: dit-il quoi faire ? Réécrivez-le mieux si vous
   pensez pouvoir.
4. Expliquez pourquoi ces deux vérifications sont dans
   `auth_required_decorator(func)` (exécuté une fois par vue) et **pas** dans
   `function_wrapper` (exécuté à chaque requête).
5. Écrivez malgré tout le test d'autorisation qui protège le comportement:

```python
def test_un_user_ne_peut_pas_editer_un_autre_profil(client):
    ...
```

Pourquoi ce test reste-t-il utile, alors que la mauvaise configuration est
maintenant impossible ?

**Critère de réussite** — les deux configurations lèvent une erreur au démarrage,
et votre test passe avec le code correct.

---

## 3. Tenter une escalade de privilèges

**Objectif** — vérifier que « caché dans le template » n'est pas « protégé ».

Connecté en `test` (rôle USER), essayez de vous attribuer le rôle ADMIN en
postant le champ `roles` que le template ne vous affiche pas:

```bash
# récupérez d'abord le jeton CSRF de la page /users/<votre id>/edit
curl -X POST http://localhost:8080/users/2/edit \
     -b cookies.txt \
     -d "email=test@example.com&description=hop&roles=2&csrf_token=<jeton>"
```

Questions:

1. le rôle est-il attribué ?
2. quelle ligne, dans quel fichier, bloque l'opération ?
3. supprimez cette ligne (`if current_user.is_admin():`) et refaites l'essai:
   qu'obtenez-vous ? Remettez-la.
4. le champ `roles` était pourtant validé par WTForms (la valeur `2` existe bien).
   Pourquoi la validation ne suffit-elle pas ?

**Critère de réussite** — vous savez énoncer la différence entre *valider une
donnée* et *autoriser une opération*.

---

## 4. Le hachage, de près

**Objectif** — comprendre ce qui est stocké, et pourquoi c'est lent.

Dans un shell Python:

```python
from argon2 import PasswordHasher
import time

ph = PasswordHasher()
print(ph.hash("admin"))
print(ph.hash("admin"))          # comparez les deux
debut = time.perf_counter(); ph.hash("admin"); print(time.perf_counter() - debut)
```

Questions:

1. pourquoi les deux hash diffèrent-ils ? Où est le sel ?
2. combien de temps prend un `hash()` ? Combien de mots de passe un attaquant
   peut-il tester par seconde avec ça, contre un SHA-256 (~µs) ?
3. que renvoie `ph.verify(hash, "mauvais")` ? (Attention: ce n'est pas `False`.)
4. dans `UserService.login`, à quoi sert le `hash()` fait « dans le vide » quand
   l'utilisateur est inconnu ? Mesurez le temps de réponse de `/login` avec un
   compte inexistant, avant et après avoir commenté cette ligne.

**Critère de réussite** — vous pouvez expliquer une *timing attack* en deux
phrases, avec vos mesures.

---

## 5. Durcir la session

**Objectif** — connaître les options de cookie qui comptent.

1. Regardez le cookie `session` dans les outils de développement: modifiez un
   caractère, rechargez. Que se passe-t-il, et pourquoi ?
2. Changez `SECRET_KEY` dans `.env.local`, relancez le serveur, rechargez:
   expliquez.
3. Ajoutez à `app/__init__.py`:

```python
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,     # déjà le défaut: pourquoi est-ce utile ?
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=not app.debug,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
```

Pour **chacune** des quatre options, écrivez une phrase: quelle attaque ou quel
inconfort elle traite. Et pourquoi `SECURE` est conditionné au debug.

**Critère de réussite** — quatre phrases justes, et l'application fonctionne
toujours en local.

---

## 6. Limiter les tentatives de connexion

**Objectif** — combler un manque réel de l'application.

Aujourd'hui, on peut essayer des mots de passe en boucle. Implémentez une
limitation:

- au bout de 5 échecs pour un même nom d'utilisateur, refuser pendant 5 minutes;
- le message affiché ne doit pas révéler si le compte existe;
- le compteur doit survivre au redémarrage du serveur… ou pas: discutez le choix
  entre la session, un dictionnaire en mémoire, et une table.

Questions:

- où placez-vous le compteur: controller, `UserService`, `AuthService` ? Pourquoi ?
- un attaquant qui change de nom d'utilisateur à chaque essai est-il ralenti ?
  Que faudrait-il compter en plus ?

**Critère de réussite** — six tentatives de suite sur `admin` avec un mauvais mot
de passe aboutissent à un refus, et le bon mot de passe est refusé aussi pendant
la pénalité.

---

## 7. Changer son mot de passe

**Objectif** — écrire une fonctionnalité complète, avec la vérification qui
compte.

Ajoutez une page « changer mon mot de passe » (`GET/POST /profile/password`):

- trois champs: mot de passe **actuel**, nouveau, confirmation;
- le service doit **vérifier l'ancien mot de passe** avant de changer;
- accessible uniquement à l'utilisateur connecté, pour lui-même;
- après changement: message de confirmation.

Questions:

- pourquoi demander l'ancien mot de passe alors que la personne est déjà
  connectée ?
- où mettez-vous la vérification: formulaire (validator) ou service ? Pourquoi ?

**Critère de réussite** — impossible de changer le mot de passe sans connaître
l'ancien, et le nouveau permet de se reconnecter.

---

## 8. Un rôle intermédiaire

**Objectif** — toucher au décorateur, pas seulement l'utiliser.

Ajoutez un rôle `MANAGER`: il peut créer et modifier des articles, mais **pas**
les supprimer, ni gérer les utilisateurs.

1. dans `RoleSeed`;
2. sur les décorateurs de `item_controller.py`;
3. relisez la règle « un ADMIN passe partout » (la première du décorateur):
   pourquoi existe-t-elle, et que se passerait-il sans elle pour un ADMIN qui
   n'aurait pas MANAGER ?
4. faites accepter une liste: `@auth_required(level=["MANAGER", "ADMIN"])`.
   Gardez la compatibilité avec l'écriture actuelle (une simple chaîne).

**Critère de réussite** — un compte MANAGER peut éditer un article et reçoit un
refus sur la suppression; un ADMIN peut tout faire; la matrice de l'exercice 1
reste valable.
