# 16 — Limiter le débit (rate limiting)

Fichiers: `app/framework/rate_limiter.py`, `app/templates/errors/429.html`

Le verrou du chapitre 15 protège **un compte**. Ce limiteur protège **le serveur**,
et ralentit celui qui essaie mille comptes différents avec le mot de passe
`123456`.

Quatrième morceau du framework maison, dans le même esprit que l'injecteur et le
seeding: une centaine de lignes qu'on lit, plutôt qu'une bibliothèque qu'on subit.

## Deux niveaux

```python
# global, dans before_request: 240 requêtes/minute/IP
rate_limiter = RateLimiter(app)

# par route, avec le décorateur:
@app.route('/login', methods=['GET', 'POST'])
@rate_limit(10, 60)
@inject
def login(...):
```

La limite globale absorbe un client qui s'emballe. Les limites par route protègent
ce qui **coûte cher** (hachage argon2) ou ce qui **part vers l'extérieur**:

| Route | Limite | Pourquoi |
|---|---|---|
| `/login` | 10/min | complète le verrou par compte du chapitre 15 |
| `/register` | 5/min | création de comptes en série |
| `/password/forgot` | 5/min | **envoie un mail** — sinon on inonde une boîte |
| `/email/verify/resend` | 3/min | envoie un mail aussi |

Le décorateur se place **sous** `@app.route` (comme `@inject`): c'est la fonction
décorée que Flask doit enregistrer.

## Fenêtre fixe: simple, et imparfait

```python
window_id = now // window          # numéro de tranche
key = (f"{bucket}:{ip}", window_id)
```

Toutes les requêtes d'une même tranche partagent un compteur; les tranches passées
sont abandonnées. C'est le plus lisible des algorithmes — et son défaut est réel:
**on peut envoyer 2× la limite à cheval sur deux fenêtres** (fin de l'une, début de
l'autre).

Ce défaut a rendu non déterministe le premier test écrit pour ce chapitre: 250
requêtes réparties 120/130 sur deux fenêtres ne dépassaient 240 dans aucune des
deux. Les alternatives: fenêtre glissante (garder les horodatages, plus de
mémoire) ou *token bucket* (un seau qui se remplit à débit constant).

## 429 et `Retry-After`

```python
return response, 429, {'Retry-After': str(retry_after)}
```

Renvoyer une page 200 « réessayez plus tard » serait **invisible** pour un client
automatique. Le code `429` et l'en-tête `Retry-After` sont ce que lisent les
navigateurs, les bibliothèques HTTP et les robots pour ralentir d'eux-mêmes.

## `remote_addr` n'est pas l'IP du client derrière un proxy

Derrière un reverse proxy (ou le WAF du chapitre 18), `remote_addr` est **le
proxy**: tous les visiteurs partagent alors la même limite, et le premier attaquant
bloque le site entier. La vraie IP arrive dans `X-Forwarded-For`, mais cet en-tête
se falsifie — d'où `ProxyFix` (chapitre 17), configuré avec le **nombre exact** de
proxys de confiance.

## Les statiques sont exemptés

```python
if request.endpoint == 'static':
    return None
```

Une page charge dix fichiers statiques: sans exemption, on épuise le quota en trois
pages.

## Les limites de cette implémentation

Elles sont dans la docstring du code, et elles comptent autant que le code:

- compteur **en mémoire** — pas partagé entre processus, perdu au redémarrage;
- inefficace contre un attaquant **distribué** sur mille IP;
- il consomme déjà un processus Python par requête, ce qu'un attaquant cherche
  précisément.

D'où la suite: Redis pour le partage (`Flask-Limiter` le fait très bien), et un
filtrage **en amont** — reverse proxy, WAF, CDN.

## L'interrupteur de test

`RATE_LIMIT_ENABLED=False` dans les tests: une suite qui envoie 40 requêtes en
trois secondes se ferait limiter elle-même. C'est un réglage normal — à condition
d'avoir **au moins un test qui vérifie que le limiteur fonctionne**, sinon on
désactive une protection que plus personne ne contrôle.
