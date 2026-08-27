# 20 — Refresh token

Fichiers: `app/models/refresh_token.py`,
`app/services/refresh_token_service.py`, `app/services/auth_service_jwt.py`

Le chapitre 19 laissait un dilemme: un access token long est dangereux (on ne peut
pas le révoquer), un access token court est insupportable (reconnexion toutes les
15 minutes). La paire **access + refresh** règle les deux.

## La paire access + refresh

| | Access token | Refresh token |
|---|---|---|
| Durée | 15 min | 7 jours |
| Forme | JWT signé | 32 octets aléatoires |
| Côté serveur | rien | ligne en base, **hachée** |
| Vérification | signature seule | une requête, révocable |
| `SameSite` | `Lax` | `Strict` |

Le refresh token n'est pas un JWT: il n'a rien à transporter. Il est stocké haché
(sha256) comme un mot de passe — une fuite de la table ne donne aucune session.

**Rotation**: chaque renouvellement consomme l'ancien et en émet un nouveau dans
la même `family_id`.

**Détection de rejeu**: si un token déjà consommé revient, c'est soit deux onglets
maladroits, soit un vol. Indiscernable, donc on choisit la sécurité: **révocation
de toute la famille**. Le vrai utilisateur se reconnecte, l'attaquant ne peut pas.
Ce coût doit être documenté avant qu'un utilisateur ne se plaigne.

**Révocation réelle**: à la déconnexion (supprimer le cookie ne suffit pas, une
copie du token fonctionnerait encore) et au changement de mot de passe
(`revoke_all_for_user`) — sinon la victime croit avoir reprisle contrôle alors que
l'attaquant garde l'accès.

## La limite qui reste

Un access token déjà émis **ne peut pas être rappelé**: après révocation du
refresh token, il continue de fonctionner jusqu'à son expiration. La fenêtre vaut
donc `JWT_ACCESS_MINUTES` — c'est pour ça qu'il est court.

À nuancer depuis le chapitre 19: comme les droits sont relus en base à chaque
requête, désactiver ou supprimer le compte coupe l'accès **immédiatement**, sans
attendre l'expiration. Ce qui reste impossible, c'est d'invalider **un** token en
particulier sans toucher au compte. Le faire demanderait une liste des `jti`
révoqués, consultée à chaque requête: c'est faisable, et c'est exactement l'état
serveur que le JWT prétendait supprimer.

## Comparatif des trois approches

| Critère | Session (09) | JWT seul (19) | JWT + refresh (20) |
|---|---|---|---|
| SQL par requête HTTP | 2 (compte + rôles) | les mêmes 2 | idem (+1 au renouvellement) |
| Révocation d'un compte | immédiate | immédiate | immédiate |
| Révocation d'un token volé | immédiate | non (≤ `exp`) | oui pour le refresh, ≤ 15 min pour l'access |
| État serveur | l'identité de session | aucun | table des refresh |
| API mobile | mal adapté | oui | oui |
| Complexité | faible | moyenne | élevée |

Pour une application interne, la session suffit et coûte trois lignes. La paire
JWT+refresh se justifie quand plusieurs clients (web, mobile, services) doivent
s'authentifier, ou quand plusieurs services doivent vérifier un token sans appeler
une base commune.

## Ce qui n'est pas fait

`purge_expired()` existe mais rien ne l'appelle: la table grossit. Une tâche
planifiée (cron, commande CLI) est nécessaire — c'est un exercice de l'étape 15.
