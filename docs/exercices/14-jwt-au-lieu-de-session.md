# Exercices — Étape 14

## 1. Ouvrir un token

**Objectif** — comprendre qu'un JWT est **signé**, pas **chiffré**.

1. Connectez-vous, copiez la valeur du cookie `access_token`.
2. Décodez-le sans clé:
   ```python
   import base64, json
   entete, charge, signature = token.split('.')
   print(json.loads(base64.urlsafe_b64decode(charge + '==')))
   ```
3. Que voyez-vous ? Est-ce grave ? Qu'est-ce qui NE doit jamais s'y trouver ?
4. Modifiez `roles` dans la charge, réencodez, remettez le cookie. Que se
   passe-t-il, et quelle partie du token vous trahit ?

**Critère de réussite** — vous savez expliquer la différence entre signé et
chiffré, et ce qu'on peut mettre dans un token.

## 2. L'attaque `alg=none`

**Objectif** — la faille JWT la plus connue.

1. Fabriquez un token sans signature:
   ```python
   import jwt
   faux = jwt.encode({'sub': '1', 'roles': ['ADMIN'], 'username': 'pirate'},
                     key="", algorithm=None)
   ```
2. Présentez-le. Il est refusé: **où** exactement ?
3. Retirez `algorithms=[...]` de `jwt.decode` et réessayez. Que se passe-t-il ?
4. Remettez-le. Question: pourquoi PyJWT exige-t-il ce paramètre, alors que
   d'autres bibliothèques historiques ne le faisaient pas ?

**Critère de réussite** — vous avez vu l'attaque réussir sans la liste blanche, et
échouer avec.

## 3. Le CSRF n'a pas disparu

**Objectif** — démonter l'idée reçue.

1. Connectez-vous. Depuis un fichier HTML **local** (`file://`), écrivez un
   formulaire qui poste vers `http://localhost:8080/items/1/delete`.
2. Sans jeton CSRF: que se passe-t-il ? Quel code HTTP ?
3. Désactivez `CSRFProtect` et refaites l'essai. Que se passe-t-il maintenant ?
4. Le cookie est `SameSite=Lax`: en quoi ça aide déjà ? Pourquoi ne suffit-il pas ?
5. Comment le problème disparaîtrait-il avec un token envoyé dans un **en-tête** ?

**Critère de réussite** — vous savez énoncer la règle: token dans un cookie =
protection CSRF obligatoire.

## 4. Le compromis des données périmées

**Objectif** — mesurer la fenêtre de péremption.

1. Connectez-vous en `test`. En tant qu'admin (autre navigateur), donnez-lui le
   rôle ADMIN.
2. Le compte `test` voit-il tout de suite les pages d'administration ? Au bout de
   combien de temps ?
3. Inversement: retirez-lui ADMIN. Pendant combien de temps garde-t-il l'accès ?
   **C'est le scénario qui compte** (un compte compromis qu'on essaie de couper).
4. Trois solutions possibles: token court, liste de révocation, rechargement
   systématique depuis la base. Implémentez-en une et dites ce qu'elle coûte.
5. Regardez comment le projet traite déjà le cas `email_verified` dans
   `get_current_user()`. Pourquoi ne relit-on la base que si le claim est
   défavorable ?

**Critère de réussite** — un chiffre (la fenêtre en minutes) et une solution
implémentée avec son coût.

## 5. Revenir à la session, puis repartir

**Objectif** — vérifier que l'interface fait bien son travail.

1. Commentez le `@injectable` de `AuthServiceJwt`, décommentez celui de
   `AuthServiceImpl`.
2. Relancez. Combien de fichiers avez-vous modifiés ? L'application fonctionne-t-elle
   à l'identique ?
3. Laissez les **deux** décorateurs actifs: qui gagne ? Pourquoi est-ce dangereux ?
   Comment l'injecteur pourrait-il détecter le conflit et refuser de démarrer ?
   Implémentez-le.

**Critère de réussite** — l'injecteur lève une erreur explicite si deux
implémentations réclament la même `base`.

## 6. Une API à côté des pages

**Objectif** — utiliser le mode en-tête.

1. Ajoutez `POST /api/login` qui renvoie le token en JSON au lieu de poser un
   cookie (`class Meta: csrf = False` sur le formulaire — pourquoi est-ce
   acceptable ici ?).
2. Appelez `/api/users` avec `Authorization: Bearer <token>` (la route existante
   fonctionne déjà: pourquoi ?).
3. Comparez: pour un client mobile, quels sont les avantages et les risques du
   mode en-tête par rapport au cookie ?

**Critère de réussite** — deux clients (navigateur et `curl`) utilisent les mêmes
routes protégées, par deux mécanismes de transport différents.

## 7. HS256 ou RS256 ?

**Objectif** — savoir choisir l'algorithme.

Nous signons en HS256 (secret partagé).

1. Que se passe-t-il si trois services différents doivent **vérifier** nos tokens ?
   Combien de copies du secret existent alors ?
2. Passez en RS256 (paire de clés): qui a besoin de la clé privée, qui n'a besoin
   que de la publique ?
3. Implémentez-le (générez la paire avec `openssl`, adaptez `encode`/`decode`).
4. Attaque classique associée: la **confusion d'algorithme** (présenter un token
   HS256 signé avec la clé publique à un serveur qui attend du RS256). Pourquoi
   `algorithms=['RS256']` la bloque-t-elle ?

**Critère de réussite** — l'application signe en RS256, et un token HS256 signé
avec la clé publique est refusé.
