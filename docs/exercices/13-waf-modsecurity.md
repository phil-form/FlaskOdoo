# Exercices — Étape 13

Le WAF doit tourner: `docker compose up -d db-example mailpit app waf`, puis
`docker compose logs -f waf` dans un second terminal.

## 1. Attaquer, et lire ce qui se passe

**Objectif** — savoir relier un blocage à une règle.

Pour chacune de ces requêtes, notez le code HTTP **et** l'`id` de la règle
déclenchée (dans les journaux):

```bash
curl -si "http://localhost:8081/items?q=1'%20OR%201=1--"
curl -si "http://localhost:8081/items?q=<img src=x onerror=alert(1)>"
curl -si "http://localhost:8081/items?f=/etc/shadow"
curl -si -A "nikto" http://localhost:8081/
curl -si -X POST -d "a=1;ls%20-la" http://localhost:8081/login
```

Puis: quel est le **score** de chaque requête ? Laquelle est passée le plus près
du seuil ?

**Critère de réussite** — un tableau requête / code / règle / score.

## 2. DetectionOnly, le mode par lequel on commence

**Objectif** — comprendre la seule façon raisonnable de déployer un WAF.

1. Passez `MODSEC_RULE_ENGINE: DetectionOnly`, redémarrez le WAF.
2. Rejouez les attaques: quels codes HTTP ?
3. Que trouve-t-on dans les journaux ? À quoi sert ce mode ?
4. Naviguez normalement sur le site pendant 5 minutes (créez un article avec une
   description technique, commandez, changez votre profil). Combien de règles
   auriez-vous déclenchées **en légitime** ?
5. Repassez en `On`.

**Critère de réussite** — vous savez expliquer pourquoi passer directement en `On`
sur une application existante est une mauvaise idée.

## 3. Provoquer un faux positif, puis le traiter

**Objectif** — le vrai travail d'exploitation d'un WAF.

1. Connecté en admin **à travers le WAF** (port 8081), créez un article dont la
   description est: `Pour supprimer: DROP TABLE items; -- attention <script>`.
2. Que se passe-t-il ? Quelle règle ?
3. Traitez-le avec la **bonne granularité**: le paramètre `description` des seules
   URL `/items/add` et `/items/<id>/edit` (voir `waf/exclusions.conf`, la règle
   1000 est déjà écrite: vérifiez qu'elle s'applique, sinon corrigez-la).
4. Vérifiez ensuite qu'une injection SQL dans un **autre** paramètre est toujours
   bloquée: l'exclusion doit être chirurgicale.
5. Comparez avec la solution paresseuse (`SecRuleRemoveById 942100`): que
   perdez-vous ?

**Critère de réussite** — la description passe, `?q=1' OR 1=1--` est toujours
bloqué.

## 4. Ses propres règles

**Objectif** — bloquer ce que le CRS ne connaît pas.

Dans `waf/rules/`, écrivez une règle qui bloque les chemins de scanners
(`/wp-login.php`, `/admin.php`, `/phpmyadmin`, `/.env`, `/.git/config`).

```
SecRule REQUEST_URI "@rx (?i)/(wp-login|admin\.php|phpmyadmin|\.env|\.git)" \
    "id:2000,phase:1,deny,status:404,log,msg:'Scanner connu'"
```

- pourquoi répondre **404** plutôt que 403 ?
- essayez `/.env`: c'est une vraie tentative très courante. Est-ce que votre
  fichier `.env` était accessible de toute façon ? Vérifiez.

**Critère de réussite** — les cinq chemins renvoient 404 et apparaissent dans les
journaux.

## 5. Ce que le WAF ne protège pas

**Objectif** — la limite fondamentale, à ne jamais oublier.

1. À travers le WAF, refaites l'attaque **IDOR** de l'étape 07 (la route
   vulnérable que vous aviez ajoutée puis supprimée — remettez-la
   temporairement).
2. Le WAF la bloque-t-il ? Pourquoi ?
3. Même question pour: l'escalade de privilèges de l'étape 06 (poster `roles=2`),
   et un mot de passe `123456`.
4. Écrivez la conclusion en une phrase.

**Critère de réussite** — vous avez montré qu'une requête parfaitement formée
mais illégitime traverse le WAF sans encombre.

## 6. Le contourner

**Objectif** — savoir qu'un WAF n'est pas une frontière étanche.

Essayez de faire passer une injection SQL malgré le CRS:

- encodages multiples (`%2527`, unicode, commentaires `/**/`);
- en-tête `Content-Type` inhabituel;
- charge dans un corps JSON plutôt que dans l'URL;
- fragmentation entre plusieurs paramètres.

Notez ce qui passe et ce qui est arrêté, puis montez `PARANOIA` à 2 et
recommencez. Quel est le prix payé en faux positifs ?

**Critère de réussite** — vous avez au moins un contournement, et vous savez dire
ce que ça change dans votre façon de voir un WAF.

## 7. Le WAF fait aussi le TLS

**Objectif** — assembler les étapes 12 et 13.

1. Faites terminer le HTTPS par le WAF (l'image accepte des certificats, voir sa
   documentation) et parlez en HTTP clair à l'application.
2. Réglez `TRUSTED_PROXIES=1` côté application.
3. Vérifiez, dans l'app: `request.is_secure`, `remote_addr` (la vraie IP du
   client), le cookie `Secure`, et un `url_for(_external=True)`.
4. Sans `TRUSTED_PROXIES`, qu'est-ce qui casse exactement ?

**Critère de réussite** — le site est en HTTPS de bout en bout côté client, et
l'application voit la vraie IP.
