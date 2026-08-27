# Exercices — Étape 15

## 1. Observer la rotation

**Objectif** — voir les deux tokens vivre.

1. Connectez-vous, notez les deux cookies.
2. Attendez 15 minutes (ou réglez `JWT_ACCESS_MINUTES=1`), rechargez une page
   protégée.
3. Les deux cookies ont-ils changé ? Regardez la table:
   ```sql
   SELECT refresh_token_id, family_id, revoked_at, expires_at FROM refresh_tokens;
   ```
4. Combien de lignes après trois renouvellements ? Combien sont encore actives ?

**Critère de réussite** — vous savez lire la lignée d'une famille dans la table.

## 2. Rejouer un token volé

**Objectif** — la détection de rejeu, en pratique.

1. Notez la valeur du `refresh_token` (c'est votre « vol »).
2. Provoquez un renouvellement (access token expiré) pour que ce token soit
   consommé.
3. Présentez le token volé depuis un autre client (`set_cookie` ou un autre
   navigateur).
4. Que se passe-t-il pour l'attaquant ? Et **pour vous** ?
5. Question de conception: cette réaction (révoquer la famille) est-elle toujours
   le bon choix ? Imaginez une application où elle serait inacceptable, et ce que
   vous feriez à la place.

**Critère de réussite** — vous avez déclenché une révocation de famille et vous
savez en défendre le principe *et* le coût.

## 3. La fenêtre de compromission

**Objectif** — mesurer ce que « révocation impossible » veut dire.

1. Connectez-vous dans deux navigateurs (A et B).
2. Depuis A, changez le mot de passe (via le lien de réinitialisation).
3. Dans B: combien de temps continuez-vous à naviguer normalement ? Pourquoi ?
4. Réduisez `JWT_ACCESS_MINUTES` à 1 et refaites l'essai.
5. Distinguez deux choses que l'on confond souvent: révoquer **un compte** et
   révoquer **un token**. Désactivez le compte en base et rechargez dans B: que
   se passe-t-il, et pourquoi est-ce immédiat alors que le changement de mot de
   passe ne l'est pas ? (Réponse dans `get_current_user`, étape 14.)
6. Que faudrait-il pour révoquer **un token en particulier**, immédiatement ?
   Chiffrez le coût, et dites ce qu'il reste alors de « le JWT est sans état ».

**Critère de réussite** — un chiffre pour la fenêtre, la distinction compte /
token écrite noir sur blanc, et un avis sur le compromis.

## 4. Le ménage

**Objectif** — une table qui ne grossit pas indéfiniment.

`purge_expired()` existe, rien ne l'appelle.

1. Exposez-la en commande CLI: `flask purge-refresh-tokens`.
2. Combien de lignes après une semaine d'utilisation par 50 personnes (calculez:
   1 connexion + 1 renouvellement toutes les 15 min sur 8 h) ?
3. Faut-il aussi supprimer les tokens **révoqués** ? Attention: ils servent à la
   détection de rejeu. Combien de temps les garder ?
4. Planifiez la commande (cron, ou un conteneur `sleep`+`flask` dans
   `docker-compose`).

**Critère de réussite** — la commande tourne, et vous savez justifier votre délai
de rétention des tokens révoqués.

## 5. « Se déconnecter de partout »

**Objectif** — une fonctionnalité que les utilisateurs attendent.

1. Ajoutez à la page profil un bouton « Déconnecter tous mes appareils »
   (`revoke_all_for_user` existe déjà).
2. Affichez la liste des sessions actives: date de création, dernière rotation.
   Que faut-il ajouter au modèle pour montrer « Firefox sur Linux, hier » ?
3. Attention à la vie privée: faut-il stocker l'IP et le User-Agent ? Pendant
   combien de temps ? (Pensez au RGPD.)

**Critère de réussite** — le bouton déconnecte les autres navigateurs (au plus au
bout d'un access token), et vous avez tranché la question des données stockées.

## 6. Comparer les trois approches

**Objectif** — savoir choisir, pas seulement implémenter.

Remplissez ce tableau à partir de ce que vous avez vécu aux étapes 06, 14 et 15:

| Critère | Session (06) | JWT seul (14) | JWT + refresh (15) |
|---|---|---|---|
| Requêtes SQL par requête HTTP | | | |
| Révocation immédiate | | | |
| Fonctionne pour une API mobile | | | |
| Complexité du code | | | |
| État côté serveur | | | |
| Ce qui casse si la base tombe | | | |

Puis: pour une application interne de 50 personnes, laquelle choisiriez-vous ?
Pour une API publique avec applications mobiles ? Justifiez en trois lignes
chacune.

**Critère de réussite** — un tableau rempli et deux recommandations argumentées.

## 7. Le token dans un en-tête, côté client (plus ambitieux)

**Objectif** — le schéma des applications mono-page.

1. Faites renvoyer par `/api/login` la paire `{access, refresh}` en JSON.
2. Écrivez un petit client JavaScript qui garde l'access token **en mémoire**
   (pas dans `localStorage`: pourquoi ?) et appelle `/api/refresh` quand il reçoit
   un 401.
3. Où stockez-vous le refresh token dans ce schéma ? (Indice: un cookie httpOnly
   `SameSite=Strict` reste le moins mauvais choix — expliquez pourquoi.)

**Critère de réussite** — le client survit à l'expiration de l'access token sans
que l'utilisateur retape son mot de passe.
