# Exercices — Étape 11

## 1. Voir la fenêtre fixe échouer

**Objectif** — constater le défaut de l'algorithme, pas seulement le lire.

1. Réglez `RATE_LIMIT_GLOBAL_MAX=10` et `RATE_LIMIT_GLOBAL_WINDOW=10`.
2. Écrivez un script qui envoie 10 requêtes juste avant la fin d'une fenêtre,
   puis 10 juste après (`time.time() % 10` vous dit où vous êtes).
3. Combien de requêtes passent en 2 secondes ? Comparez à la limite annoncée.
4. Corrigez avec une **fenêtre glissante**: gardez les horodatages des requêtes
   et comptez celles des N dernières secondes. Quel est le coût en mémoire ?
5. Variante: implémentez un **token bucket** (un seau qui se remplit à débit
   constant). Lequel préférez-vous, et pourquoi ?

**Critère de réussite** — votre version ne laisse plus passer 2× la limite à
cheval sur deux fenêtres.

## 2. Choisir les bonnes limites

**Objectif** — une limite trop basse est une panne, trop haute ne sert à rien.

Pour chaque route, proposez une limite chiffrée **et sa justification**:
`/` , `/items`, `/items/add`, `/login`, `/password/forgot`, `/basket/add`.

Puis: mesurez combien de requêtes une navigation normale de 2 minutes déclenche
(regardez les journaux). Vos limites laissent-elles vivre un utilisateur pressé ?

**Critère de réussite** — un tableau route/limite/justification, et aucune limite
qui gêne un usage normal.

## 3. Le piège du proxy

**Objectif** — comprendre pourquoi `remote_addr` ne suffit pas.

1. Lancez l'application derrière un proxy simple:
   `docker run -p 8090:80 -e ... nginx` avec un `proxy_pass` vers votre app.
2. Faites-vous limiter, puis demandez à quelqu'un d'autre (autre IP) d'essayer:
   est-il limité lui aussi ? Pourquoi ?
3. Regardez ce que vaut `request.remote_addr` (journalisez-le).
4. Activez `TRUSTED_PROXIES=1` (étape 12) et recommencez.
5. Essayez ensuite de contourner la limite en envoyant vous-même
   `X-Forwarded-For: 1.2.3.4`. Que se passe-t-il avec `TRUSTED_PROXIES=1` ? Et
   avec `TRUSTED_PROXIES=2` alors qu'il n'y a qu'un proxy ?

**Critère de réussite** — vous savez expliquer pourquoi le nombre de proxys
déclaré doit être **exact**.

## 4. Ne pas limiter ce qu'il ne faut pas

**Objectif** — éviter les faux positifs.

1. Que se passe-t-il si un utilisateur charge une page avec 20 images ?
   (Les statiques sont exemptés: retirez l'exemption et regardez.)
2. Faut-il limiter les requêtes des utilisateurs **connectés** de la même façon
   que les anonymes ? Implémentez une limite par utilisateur (plus généreuse)
   quand `current_user` existe.
3. Et le moniteur de disponibilité qui interroge `/` toutes les 10 secondes ?
   Comment l'exempter proprement ?

**Critère de réussite** — un utilisateur connecté et une sonde de supervision ne
se font jamais limiter.

## 5. Redis et le partage entre processus

**Objectif** — voir la limite du compteur en mémoire.

1. Lancez deux processus Flask sur deux ports, derrière un proxy qui alterne.
2. Constatez que la limite est doublée. Expliquez.
3. Passez le compteur dans Redis (`INCR` + `EXPIRE`, quatre lignes).
4. **La question qui compte**: si Redis tombe, votre limiteur laisse-t-il tout
   passer (`fail-open`) ou bloque-t-il tout (`fail-closed`) ? Codez le choix
   explicitement, avec un commentaire qui le justifie.

**Critère de réussite** — la limite est respectée globalement avec deux processus.

## 6. Comparer avec l'existant

**Objectif** — savoir quand arrêter d'écrire son propre outil.

Installez `Flask-Limiter` et refaites la même chose.

- combien de lignes en moins ?
- qu'apporte-t-il que notre version n'a pas (stockage, stratégies, en-têtes
  `X-RateLimit-*`, exemptions) ?
- qu'est-ce qu'on perd en lisibilité ?
- pour ce projet de formation, lequel garderiez-vous ? Et pour une application en
  production ?

**Critère de réussite** — un avis argumenté, appuyé sur les deux versions
tournées.
