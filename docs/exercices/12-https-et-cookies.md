# Exercices — Étape 12

## 1. Voir le cookie changer

**Objectif** — relier chaque option à ce qu'on observe.

1. Connectez-vous en HTTP, notez les attributs du cookie `session` (outils de
   développement → Application → Cookies).
2. `HTTPS=True python main.py`, reconnectez-vous: qu'est-ce qui change ?
3. Passez `DEBUG=False` (dans `.env.local`) en restant en HTTP: connectez-vous.
   Que se passe-t-il, et **pourquoi** ? (C'est le piège de `Secure` en local.)
4. Dans la console du navigateur, tapez `document.cookie`: voyez-vous la session ?
   Retirez `SESSION_COOKIE_HTTPONLY` et refaites l'essai.

**Critère de réussite** — vous savez dire, pour chaque attribut, ce qu'un
attaquant peut faire quand il manque.

## 2. Voler une session en clair

**Objectif** — rendre le risque tangible (sur VOTRE machine uniquement).

1. Lancez l'app en HTTP et capturez votre propre trafic:
   `sudo tcpdump -i lo -A -s 0 'tcp port 8080' | grep -i cookie`
2. Connectez-vous. Retrouvez le cookie dans la capture.
3. Copiez-le dans un autre navigateur (outils de développement → Cookies):
   êtes-vous connecté ?
4. Refaites tout en HTTPS: que voit `tcpdump` ?

**Critère de réussite** — vous avez volé votre propre session en HTTP, et échoué
en HTTPS.

## 3. Session fixation

**Objectif** — comprendre la rotation en la retirant.

1. Commentez `session.clear()` dans `AuthServiceImpl.login`.
2. Simulez l'attaque: dans un client de test, forcez une valeur de session
   (`with client.session_transaction() as s: s['piege'] = 'attaquant'`),
   connectez-vous, puis vérifiez que `piege` est toujours là.
3. Expliquez en quoi c'est un problème quand la valeur pré-posée est
   l'identifiant de session lui-même (cas d'un serveur qui en utilise un).
4. Remettez la rotation. Écrivez le test qui échoue sans elle.

**Critère de réussite** — un test automatique qui distingue les deux versions.

## 4. Construire une vraie CSP

**Objectif** — passer d'une CSP « large » à une CSP utile.

La CSP actuelle autorise `'unsafe-inline'`, ce qui laisse passer l'essentiel des
XSS. Resserrez-la:

1. retirez `'unsafe-inline'` de `script-src` et rechargez le site: qu'est-ce qui
   casse ? (Regardez la console du navigateur.)
2. déplacez les scripts inline des templates dans un fichier de `static/`;
3. pour ce qui doit rester inline, utilisez un **nonce** par requête;
4. ajoutez `report-uri` (ou `report-to`) et une route qui journalise les
   violations. Naviguez et lisez ce qui remonte.

**Critère de réussite** — le site fonctionne sans `'unsafe-inline'` sur
`script-src`.

## 5. Derrière un proxy

**Objectif** — configurer `ProxyFix` juste.

1. Mettez un nginx devant l'app (conteneur, `proxy_pass`), en HTTP.
2. Avec `TRUSTED_PROXIES=0`: que vaut `request.remote_addr` ? Le cookie `Secure`
   part-il si nginx fait le TLS ?
3. Passez à `1`. Vérifiez `remote_addr`, `request.is_secure`, et un
   `url_for(..., _external=True)`.
4. Attaque: envoyez `X-Forwarded-For: 6.6.6.6` depuis votre navigateur. Que voit
   l'application avec `TRUSTED_PROXIES=1` ? Avec `2` ? Concluez.

**Critère de réussite** — l'IP vue par l'app est la vraie, et un en-tête injecté
par le client ne la change pas.

## 6. Auditer les en-têtes

**Objectif** — utiliser les outils que les auditeurs utilisent.

1. `curl -sI https://localhost:8080/ -k` : listez les en-têtes de sécurité.
2. Comparez avec la checklist de l'OWASP Secure Headers Project. Lesquels
   manquent ? Sont-ils pertinents ici ?
3. Ajoutez `Permissions-Policy` (désactivez caméra, micro, géolocalisation).
4. Pourquoi `X-XSS-Protection` ne figure-t-il pas dans notre liste ? (Cherchez:
   il est obsolète, et pourquoi.)

**Critère de réussite** — vous savez justifier chaque en-tête présent **et**
chaque en-tête volontairement absent.
