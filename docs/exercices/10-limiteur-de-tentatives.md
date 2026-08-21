# Exercices — Étape 10

## 1. Mesurer avant de protéger

**Objectif** — chiffrer le risque, au lieu de le supposer.

1. Chronométrez une tentative de connexion échouée (`time curl -X POST ...`).
2. Combien d'essais par heure, en séquentiel ? Avec 10 requêtes en parallèle ?
3. Une liste de 10 000 mots de passe courants: combien de temps pour l'épuiser
   **sans** le verrou ? Et avec ?

**Critère de réussite** — trois nombres, et une phrase qui dit si le verrou est
utile ici.

## 2. Le déni de service ciblé

**Objectif** — comprendre le défaut de l'approche.

1. Verrouillez volontairement le compte `admin` (5 échecs).
2. En tant qu'`admin` légitime, essayez de vous connecter: décrivez l'expérience.
3. Un attaquant peut donc vous empêcher de travailler. Proposez deux atténuations
   et implémentez-en une:
   - ne verrouiller que la **combinaison** (identifiant + IP);
   - ralentir progressivement (1 s, 2 s, 4 s, 8 s…) au lieu de bloquer;
   - un captcha après 3 échecs.
4. Quel effet a votre choix sur un attaquant distribué (mille IP) ?

**Critère de réussite** — le compte légitime reste utilisable depuis son IP
habituelle, l'attaquant est ralenti.

## 3. Par IP aussi

**Objectif** — fermer le contournement « un essai par compte ».

Un attaquant essaie `123456` sur 500 comptes différents: aucun compteur par
compte ne dépasse 1.

1. Ajoutez un compteur par IP (5 échecs toutes IP confondues -> blocage de l'IP).
2. Où le mettre: le même service, ou un autre ? Justifiez.
3. Que se passe-t-il pour 30 personnes derrière le même NAT d'entreprise ?
   Comment le détecter avant de mettre en production ?

**Critère de réussite** — 5 échecs sur 5 comptes différents depuis la même IP
bloquent la 6e tentative.

## 4. Le ménage

**Objectif** — une table qui ne grossit pas indéfiniment.

1. Écrivez `purge()` dans le service: supprimer les lignes sans échec récent et
   sans verrou actif.
2. Exposez-la en commande CLI (`flask purge-login-attempts`).
3. Comment la faire tourner tous les jours ? (cron, `docker compose` + `sleep`,
   APScheduler: comparez.)

**Critère de réussite** — la commande supprime les vieilles lignes et laisse les
verrous en cours.

## 5. Journaliser ce qui compte

**Objectif** — pouvoir répondre à « est-ce qu'on nous attaque ? ».

1. Le service journalise déjà un `warning` au verrouillage. Ajoutez l'IP.
2. Écrivez la commande shell qui, à partir des journaux, sort le top 10 des
   identifiants visés.
3. Question: faut-il journaliser le **mot de passe essayé** ? Argumentez (et
   allez voir ce que dit l'OWASP Logging Cheat Sheet).

**Critère de réussite** — vous savez extraire des journaux la liste des comptes
attaqués, et vous savez pourquoi on ne journalise jamais un mot de passe.

## 6. Passer à Redis (plus ambitieux)

**Objectif** — voir ce que change un stockage partagé.

1. Remplacez la table par Redis (`redis` dans docker-compose, `INCR` + `EXPIRE`).
2. Qu'est-ce qui devient plus simple ? (l'expiration automatique, la vitesse)
3. Qu'est-ce qui devient plus fragile ? (une dépendance de plus, et si Redis
   tombe: on bloque tout, ou on laisse tout passer ?)
4. Écrivez ce choix noir sur blanc dans le code (`fail-open` ou `fail-closed`) et
   justifiez-le.

**Critère de réussite** — le verrou fonctionne avec deux processus Flask
simultanés, ce que la version en mémoire ne permettait pas.
