# Exercices — Étape 08

Le sujet: les mails en développement, et un token qu'on ne peut ni forger, ni
rejouer, ni utiliser éternellement.

Mailpit doit tourner: `docker compose up -d mailpit`, interface sur
<http://localhost:8025>.

---

## 1. Lire un mail comme un développeur

**Objectif** — savoir inspecter un envoi au lieu de le supposer.

1. Demandez un lien pour `test@example.com`, ouvrez Mailpit.
2. Affichez la **source** du message (onglet *Source* / *Raw*). Repérez:
   `From`, `To`, `Subject`, `Content-Type`, et le corps.
3. D'où vient chacun de ces éléments dans le code ? Citez le fichier et la ligne.
4. Le lien est absolu (`http://localhost:8080/...`): qu'est-ce qui le rend absolu ?
   Que se passerait-il avec un lien relatif dans un client mail ?
5. Modifiez `app/templates/emails/password_reset.txt` (signature, tutoiement,
   durée annoncée) et vérifiez le résultat dans Mailpit.

**Critère de réussite** — vous savez retrouver dans le code chaque partie du mail
reçu.

---

## 2. Attaquer le token

**Objectif** — comprendre les trois protections en essayant de les contourner.

Pour **chaque** tentative: prédisez le résultat par écrit, puis testez.

| Tentative | Votre prédiction | Résultat |
|---|---|---|
| changer le dernier caractère du token dans l'URL | | |
| décoder la partie centrale du token (`base64.urlsafe_b64decode`, ajoutez du padding `==`) | | |
| fabriquer un token avec un autre `user_id` et le re-signer sans la `SECRET_KEY` | | |
| réutiliser le lien **après** avoir changé le mot de passe | | |
| `PASSWORD_RESET_MAX_AGE=1` dans `.env.local`, attendre 3 s, cliquer | | |

Puis répondez:

- le contenu du token est-il **secret** ? Est-ce grave ?
- quelle protection empêche le rejeu, et **comment**, sans aucune table en base ?
- à quoi sert le `salt='password-reset'` ?

**Critère de réussite** — les cinq tentatives échouent, et vous pouvez nommer la
protection qui a joué dans chaque cas.

---

## 3. L'énumération de comptes

**Objectif** — voir ce qu'une réponse « utile » peut révéler.

1. Demandez un lien pour `inconnu@example.com`, puis pour `test@example.com`.
   Comparez **exactement**: le texte affiché, le code HTTP, l'URL finale, et le
   temps de réponse.
2. Modifiez le controller pour afficher « adresse inconnue » quand c'est le cas.
3. Écrivez le script (5 lignes de `curl` ou de `requests`) qui, à partir d'une
   liste de 100 adresses, dirait lesquelles ont un compte.
4. Remettez le code d'origine. Vérifiez qu'un compte **désactivé** ne reçoit rien,
   et que la réponse est la même que pour un compte actif.

**Critère de réussite** — impossible de distinguer les deux cas depuis l'extérieur,
et vous avez le script qui le prouve (il ne trouve rien).

---

## 4. Les règles de mot de passe selon l'environnement

**Objectif** — manipuler la ternaire, et comprendre son moment d'évaluation.

1. En `DEBUG=True`, inscrivez-vous avec `abcd`: accepté.
2. `DEBUG=False` dans `.env.local`, relancez, réessayez `abcd`, puis
   `motdepasselong`, puis `MotDePasse123`. Expliquez chaque refus.
3. La ternaire est évaluée **à l'import du module**. Prouvez-le: changez `DEBUG`
   **sans** redémarrer le serveur (le reloader va relancer — coupez-le avec
   `app.debug` déjà chargé, ou testez dans un shell).
4. Ajoutez une règle: interdire les 20 mots de passe les plus courants (une liste
   en dur suffit). Où la mettez-vous pour qu'elle s'applique **aussi** à la
   réinitialisation ?

**Critère de réussite** — `Password123` est refusé s'il figure dans votre liste,
à l'inscription **et** sur la page de réinitialisation.

---

## 5. Vérification de l'adresse à l'inscription

**Objectif** — réutiliser le mécanisme du token pour un autre usage.

À l'inscription, envoyez un mail de confirmation; le compte n'est pleinement
utilisable qu'après clic.

1. `email_verified` (booléen) sur `User` + migration;
2. un token signé avec un **autre `salt`** — pourquoi est-ce important ?
3. route `GET /email/verify/<token>`;
4. décidez et justifiez: connexion refusée tant que l'adresse n'est pas vérifiée,
   ou connexion autorisée avec un bandeau ?
5. prévoyez le renvoi du mail (« je n'ai rien reçu »), avec la même prudence
   d'énumération qu'à l'exercice 3.

**Critère de réussite** — un token de vérification ne fonctionne **pas** sur
`/password/reset/<token>`, et inversement.

---

## 6. Un mail à chaque commande

**Objectif** — réutiliser `MailService` dans un autre contexte.

Au checkout (étape 07), envoyez un récapitulatif de commande à l'utilisateur.

Consignes:

- un template `app/templates/emails/commande.txt` avec les lignes du panier;
- l'envoi ne doit **jamais** faire échouer la commande: si le SMTP est en panne,
  la commande reste validée. Où placez-vous l'appel, et comment traitez-vous
  l'échec ?
- vérifiez dans Mailpit que le contenu correspond au panier validé.

**Critère de réussite** — avec `MAIL_PORT=59999` (aucun serveur), la commande
passe quand même, et l'erreur apparaît dans le journal.

---

## 7. Quand le SMTP tombe

**Objectif** — savoir ce que l'utilisateur voit quand une dépendance externe
échoue.

1. `MAIL_PORT=59999` dans `.env.local`, demandez un lien de réinitialisation.
2. La page plante-t-elle ? Où l'échec est-il rattrapé ? Que voit l'utilisateur ?
3. Est-il souhaitable qu'il ne voie **aucune** différence ? Argumentez dans les
   deux sens (sécurité contre honnêteté).
4. Que faudrait-il en production: file d'attente, réessai, supervision ?
   Esquissez la solution en cinq lignes.
5. Mesurez: combien de temps la page met-elle à répondre ? D'où vient cette
   durée ? (Indice: `timeout=5` dans `MailService`.) Quel serait le symptôme
   **sans** ce timeout ?

**Critère de réussite** — vous savez expliquer pourquoi `MailService.send()`
retourne `False` au lieu de lever une exception.

---

## 8. Limiter les demandes de réinitialisation

**Objectif** — empêcher qu'on inonde une boîte mail depuis votre application.

Aujourd'hui, on peut appeler `/password/forgot` en boucle: chaque appel envoie un
mail.

1. Limitez à un envoi par adresse toutes les 2 minutes.
2. Où gardez-vous l'information ? (Session: non — pourquoi ?)
3. La limitation doit-elle changer la réponse affichée ? Attention à l'exercice 3.
4. Que se passe-t-il si l'attaquant fait tourner les adresses ? Que compter en
   plus ?

**Critère de réussite** — dix appels d'affilée pour la même adresse produisent
**un** mail, et la page affiche toujours le même message.
