# Étape 13 — Un WAF devant l'application (OWASP ModSecurity + CRS)

Jusqu'ici toutes les protections sont **dans** l'application. Un WAF (*Web
Application Firewall*) en ajoute une **devant**: il inspecte les requêtes avant
qu'elles n'atteignent Python, reconnaît les motifs d'attaque connus, et journalise
ce qui a été tenté.

Ce n'est pas un remplacement. C'est une couche de plus, et un excellent outil
pédagogique: on voit enfin passer des attaques réelles.

---

## Démarrer

```bash
docker compose up -d db-example mailpit app waf
```

| Adresse | Quoi |
|---|---|
| <http://localhost:8081> | l'application **à travers le WAF** |
| `docker compose logs -f waf` | ce que le WAF voit et bloque |

Puis essayez, dans cet ordre:

```bash
# légitime -> 200
curl -si http://localhost:8081/items | head -1

# injection SQL -> 403
curl -si "http://localhost:8081/items?q=1'%20OR%201=1--" | head -1

# XSS -> 403
curl -si "http://localhost:8081/items?q=<script>alert(1)</script>" | head -1

# traversée de répertoire -> 403
curl -si "http://localhost:8081/items?f=../../../../etc/passwd" | head -1

# scanner reconnu à son User-Agent -> 403
curl -si -A "sqlmap/1.7" http://localhost:8081/ | head -1
```

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | **service `waf`** — `owasp/modsecurity-crs:nginx` devant l'app |
| `waf/exclusions.conf` | **nouveau** — les faux positifs de CETTE application |
| `waf/rules/README.md` | **nouveau** — où mettre ses propres règles |

Aucune ligne de Python: c'est de l'infrastructure. C'est aussi le message de
l'étape — toute la sécurité ne s'écrit pas dans l'application.

### 1. Comment c'est branché

```
navigateur → WAF (nginx + ModSecurity + CRS) → app Flask → PostgreSQL
             :8081                              :8080
```

Le WAF est un **reverse proxy**: il reçoit, inspecte, puis transmet à `BACKEND`.
Conséquence directe: pour l'application, toutes les requêtes viennent maintenant
du WAF — d'où `TRUSTED_PROXIES=1` (étape 12), sans quoi la limite de débit de
l'étape 11 est partagée par tout le monde.

### 2. ModSecurity, le CRS, et le score d'anomalie

- **ModSecurity** est le moteur: il sait lire une requête et appliquer des règles.
- Le **CRS** (*Core Rule Set*) est le jeu de règles OWASP: quelques centaines de
  motifs pour l'injection SQL, le XSS, les traversées de chemin, les scanners…
- Chaque règle qui matche **ajoute des points**. Quand le total dépasse
  `ANOMALY_INBOUND` (5 par défaut), la requête est bloquée. Ça évite qu'une seule
  règle un peu nerveuse bloque tout le monde.

Les trois réglages qui comptent:

| Variable | Effet |
|---|---|
| `MODSEC_RULE_ENGINE` | `On` (bloque), `DetectionOnly` (journalise seulement), `Off` |
| `PARANOIA` | 1 à 4: plus haut = plus de règles **et** plus de faux positifs |
| `ANOMALY_INBOUND` | score à partir duquel on bloque |

**On commence TOUJOURS en `DetectionOnly`** sur une application existante: on
regarde ce qui aurait été bloqué pendant quelques jours, on traite les faux
positifs, et seulement ensuite on passe à `On`.

### 3. Lire les journaux, c'est 80 % du travail

```bash
docker compose logs -f waf | grep -o '"ruleId":"[0-9]*"' | sort | uniq -c | sort -rn
```

Chaque blocage donne l'`id` de la règle, le paramètre concerné, et le score. C'est
avec ça qu'on décide: vrai positif (on laisse) ou faux positif (on exclut).

Batterie d'attaques passée sur cette étape, et ce que le CRS a retenu:

| Requête | Résultat | Règles |
|---|---|---|
| `/items?q=1' OR 1=1--` | **403** | 942100 (SQLi) |
| `/items?q=<script>…` | **403** | 941160, 941390 (XSS) |
| `/items?f=../../etc/passwd` | **403** | 930110, 930120 (LFI) |
| `/items?c=;cat /etc/passwd` | **403** | 932160 (RCE) |
| `User-Agent: sqlmap/1.7` | **403** | 913100 (scanner) |
| `X-Api: ${jndi:ldap://…}` | **403** | 944150 (log4shell) |
| `/`, `/items`, `/login`, `/seed` | 200 | — |

### 4. Les faux positifs, et comment NE PAS les traiter

Un WAF générique ne connaît pas votre application. Il voit passer des chaînes qui
*ressemblent* à des attaques. Exemple réel de ce projet: la description d'un
article peut contenir `SELECT`, `<script>` ou `--` — on vend du matériel
informatique, on parle de code.

`waf/exclusions.conf` montre la bonne façon de faire, du plus fin au plus brutal:

1. exclure la règle pour **un paramètre d'une URL** ← viser ça;
2. l'exclure pour **une URL**;
3. la désactiver **partout** ← dernier recours.

Ce qu'il ne faut **pas** faire, et qu'on voit partout: baisser `PARANOIA`, ou
repasser en `DetectionOnly` « le temps de voir ». Ça désarme le WAF sur tout le
site pour un problème local.

Autre faux positif rencontré en testant cette étape: la règle **920350**
(« Host header is a numeric IP address ») se déclenche quand on appelle le WAF par
son IP au lieu d'un nom d'hôte. D'où le `-H "Host: localhost"` dans certains
exemples — et la leçon: un WAF qui « bloque tout » est souvent un WAF qu'on
interroge mal.

### 5. Ce qu'un WAF ne fait pas

- il ne corrige **aucune** faille de l'application: une IDOR (étape 07) passe
  tranquillement, c'est une requête parfaitement légitime;
- il ne comprend pas votre logique métier;
- il se contourne (encodages, fragmentation, motifs inédits);
- mal réglé, il **casse** l'application: c'est le vrai risque de production.

Il traite le bruit de fond (scanners, exploits connus, robots) et donne de la
visibilité. Les deux valent la peine — à condition de ne pas s'en servir comme
d'une excuse pour ne pas corriger le code.

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/18-waf-modsecurity.md`](docs/18-waf-modsecurity.md)

---

## Étape suivante

[`14-jwt-au-lieu-de-session`](../14-jwt-au-lieu-de-session/) — remplacer la
session par un JWT, sans toucher aux controllers.
