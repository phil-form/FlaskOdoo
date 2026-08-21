# Étape 11 — Limiter le débit

L'étape 10 protège **un compte**. Cette étape protège **le serveur**, et ralentit
celui qui essaie mille comptes différents avec le mot de passe `123456`.

Troisième morceau du framework maison, dans le même esprit que l'injecteur et le
seeding: 100 lignes qu'on lit, plutôt qu'une bibliothèque qu'on subit.

---

## Démarrer

```bash
docker compose up -d db-example mailpit
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py
```

Rechargez `/login` onze fois de suite: la onzième renvoie une page **429**.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/framework/rate_limiter.py` | **nouveau** — le limiteur + le décorateur `@rate_limit` |
| `app/templates/errors/429.html` | **nouveau** — la page « trop de requêtes » |
| `app/__init__.py` | `RateLimiter(app)` après les controllers |
| `app/controllers/user_controller.py` | limites serrées sur 4 routes |
| `.env` | `RATE_LIMIT_ENABLED`, `RATE_LIMIT_GLOBAL_MAX`, `RATE_LIMIT_GLOBAL_WINDOW` |

### 1. Deux niveaux

```python
# global, dans before_request: 240 requêtes/minute/IP
# par route, avec le décorateur:
@app.route('/login', methods=['GET', 'POST'])
@rate_limit(10, 60)
@inject
def login(...):
```

La limite globale absorbe un client qui s'emballe. Les limites par route
protègent ce qui **coûte cher** (hachage argon2) ou ce qui **part vers
l'extérieur** (envoi de mail: `/password/forgot` à 5/min, `/email/verify/resend` à
3/min — sans quoi l'application devient un outil pour inonder une boîte mail).

### 2. Fenêtre fixe: simple, et imparfait

```python
window_id = now // window          # numéro de tranche
key = (f"{bucket}:{ip}", window_id)
```

Toutes les requêtes d'une même tranche partagent un compteur; les tranches
passées sont abandonnées. C'est le plus lisible des algorithmes — et son défaut
est réel: **on peut envoyer 2× la limite à cheval sur deux fenêtres** (fin de
l'une, début de l'autre).

Ce défaut a fait échouer le premier test écrit pour cette étape: 250 requêtes
réparties 120/130 sur deux fenêtres ne dépassaient 240 dans aucune des deux.
Le test le documente maintenant.

### 3. `remote_addr` n'est pas l'IP du client derrière un proxy

```python
return request.remote_addr or "inconnu"
```

Derrière un reverse proxy (ou le WAF de l'étape 13), `remote_addr` est **le
proxy**: tous les visiteurs partagent alors la même limite, et le premier
attaquant bloque le site entier. La vraie IP arrive dans `X-Forwarded-For`, mais
cet en-tête se falsifie — d'où `ProxyFix` à l'étape 12, configuré avec le nombre
de proxys de confiance.

### 4. 429 et `Retry-After`

Renvoyer une page 200 « réessayez plus tard » serait invisible pour un client
automatique. Le code **429** et l'en-tête **Retry-After** sont ce que lisent les
navigateurs, les bibliothèques HTTP et les robots pour ralentir d'eux-mêmes.

### 5. Les limites de cette implémentation

Elles sont écrites dans la docstring, et elles comptent autant que le code:

- compteur **en mémoire** — pas partagé entre processus, perdu au redémarrage;
- inefficace contre un attaquant **distribué** sur mille IP;
- il consomme déjà un processus Python par requête, ce qu'un attaquant cherche
  précisément.

D'où la suite logique: Redis pour le partage (Flask-Limiter le fait), et un
filtrage **en amont** — reverse proxy, WAF, CDN. C'est l'étape 13.

### 6. `RATE_LIMIT_ENABLED=False` dans les tests

Une suite de tests envoie 40 requêtes en trois secondes: sans interrupteur, elle
se ferait limiter elle-même. C'est un réglage normal, pas une triche — mais il
faut au moins un test qui vérifie que le limiteur **fonctionne**, sinon on
désactive une protection que personne ne vérifie plus.

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/16-limitation-de-debit.md`](docs/16-limitation-de-debit.md)

---

## Étape suivante

[`12-https-et-cookies`](../12-https-et-cookies/) — chiffrer le transport et
durcir les cookies.
