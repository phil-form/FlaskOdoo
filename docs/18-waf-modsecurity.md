# 18 — Un WAF devant l'application

Fichiers: `docker-compose.yml` (service `waf`), `waf/exclusions.conf`,
`waf/rules/`

Un WAF (*Web Application Firewall*) inspecte les requêtes **avant** qu'elles
n'atteignent l'application. Ici: `owasp/modsecurity-crs:nginx` — nginx +
ModSecurity + le Core Rule Set de l'OWASP.

```
navigateur → WAF (:8081) → app Flask (:8080) → PostgreSQL
```

## Les trois réglages qui comptent

| Variable | Effet |
|---|---|
| `MODSEC_RULE_ENGINE` | `On` bloque, `DetectionOnly` journalise seulement, `Off` |
| `PARANOIA` | 1 à 4: plus haut = plus de règles **et** plus de faux positifs |
| `ANOMALY_INBOUND` | score de blocage (chaque règle qui matche ajoute des points) |

Le score évite qu'une seule règle nerveuse bloque tout le monde.

**On déploie toujours en `DetectionOnly` d'abord**, on regarde ce qui *aurait* été
bloqué pendant quelques jours, on traite les faux positifs, puis on passe à `On`.
L'inverse est le meilleur moyen de couper son propre site un vendredi soir.

## Ce que ça arrête, vérifié

| Requête | Résultat | Règles CRS |
|---|---|---|
| `/items?q=1' OR 1=1--` | **403** | 942100 |
| `/items?q=<script>alert(1)</script>` | **403** | 941160, 941390 |
| `/items?f=../../../../etc/passwd` | **403** | 930110, 930120 |
| `/items?c=;cat /etc/passwd` | **403** | 932160 |
| `User-Agent: sqlmap/1.7` | **403** | 913100 |
| `X-Api: ${jndi:ldap://…}` | **403** | 944150 |
| `/`, `/items`, `/login`, `/seed` | 200 | — |

Lire les journaux est 80 % du travail:

```bash
docker compose logs -f waf | grep -o '"ruleId":"[0-9]*"' | sort | uniq -c | sort -rn
```

## Les faux positifs

Un WAF générique ne connaît pas votre application: il voit des chaînes qui
*ressemblent* à des attaques. Dans ce projet, la description d'un article peut
légitimement contenir `SELECT`, `<script>` ou `--`.

Trois niveaux de finesse, du meilleur au pire:

1. exclure la règle pour **un paramètre d'une URL** ← viser ça;
2. l'exclure pour **une URL**;
3. la désactiver **partout** ← dernier recours.

```
SecRule REQUEST_URI "@rx ^/items/(add|[0-9]+/edit)$" \
    "id:1000,phase:1,pass,nolog,\
     ctl:ruleRemoveTargetByTag=attack-sqli;ARGS:description"
```

Ce qu'il ne faut **pas** faire, et qu'on voit partout: baisser `PARANOIA` ou
repasser en `DetectionOnly` « le temps de voir ». Ça désarme le WAF sur tout le
site pour un problème local.

Faux positif rencontré en écrivant ce chapitre: la règle **920350** (« Host header
is a numeric IP address ») se déclenche quand on appelle le WAF par son IP au lieu
d'un nom d'hôte. Leçon: un WAF qui « bloque tout » est souvent un WAF qu'on
interroge mal.

## Ce qu'un WAF ne fait pas

- il ne corrige **aucune** faille applicative: une IDOR (chapitre 07) est une
  requête parfaitement légitime, elle passe;
- il ne connaît pas votre logique métier (escalade de privilèges, mot de passe
  faible: invisibles pour lui);
- il se contourne (encodages, fragmentation, motifs inédits);
- mal réglé, il **casse** l'application — c'est son vrai risque.

Il traite le bruit de fond et donne de la visibilité. Les deux valent la peine, à
condition de ne pas s'en servir d'excuse pour ne pas corriger le code.

## Conséquence pour l'application

Toutes les requêtes viennent maintenant du WAF: il faut `TRUSTED_PROXIES=1`
(chapitre 16), sinon la limite de débit du chapitre 15 est partagée par tous les
visiteurs et le premier attaquant bloque le site entier.
