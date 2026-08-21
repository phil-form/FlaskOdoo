# Étape 12 — HTTPS et sécurisation des cookies

Toutes les protections des étapes précédentes reposent sur un cookie de session.
Si ce cookie voyage en clair, ou si le JavaScript peut le lire, elles ne valent
rien: il suffit de le copier pour devenir n'importe qui.

Cette étape ferme le transport, durcit les cookies, ajoute les en-têtes de
sécurité — et la **rotation de session** à la connexion.

---

## Démarrer

```bash
docker compose up -d db-example mailpit
pip install -r requirements.txt      # + cryptography
./sqlAlchemy.sh -u
python main.py                       # http://localhost:8080

# en HTTPS local:
./certs/generer.sh
HTTPS=True python main.py            # https://localhost:8080 (certificat auto-signé)
```

Regardez le cookie `session` dans les outils de développement, en HTTP puis en
HTTPS: `HttpOnly`, `SameSite`, et `Secure` qui apparaît hors debug.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/__init__.py` | config des cookies, `ProxyFix`, en-têtes de sécurité |
| `app/services/auth_service_impl.py` | **rotation de session** à la connexion |
| `main.py` | option `HTTPS=True` (certificat local ou `adhoc`) |
| `certs/generer.sh` | **nouveau** — certificat auto-signé de développement |
| `.env` | `HTTPS`, `TRUSTED_PROXIES`, `SESSION_HOURS` |
| `requirements.txt` | `cryptography` (nécessaire à `ssl_context='adhoc'`) |

### 1. Les quatre attributs du cookie, et ce qu'ils traitent

```python
SESSION_COOKIE_HTTPONLY=True,
SESSION_COOKIE_SECURE=not app.debug,
SESSION_COOKIE_SAMESITE='Lax',
PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
```

| Attribut | Ce qu'il empêche |
|---|---|
| `HttpOnly` | qu'un XSS **vole** le cookie (il peut encore agir, mais pas l'emporter) |
| `Secure` | que le cookie parte en clair — une seule requête HTTP suffirait à le fuiter |
| `SameSite=Lax` | qu'il soit envoyé sur un POST venu d'un autre site (2e barrière anti-CSRF) |
| `PERMANENT_SESSION_LIFETIME` | qu'une session traîne indéfiniment |

`Secure` est conditionné à `app.debug`: sinon plus aucune session en local sur
`http://localhost`. `SameSite='Strict'` casserait les liens entrants (on arrive
déconnecté depuis un mail) — `Lax` est le bon défaut.

### 2. ProxyFix: sans lui, tout le durcissement tombe

En production, ce n'est pas Flask qui termine le TLS: c'est un reverse proxy (le
WAF de l'étape 13, nginx, un load balancer) qui parle **en HTTP clair** à
l'application. Sans `ProxyFix`, Flask croit donc que la requête est arrivée en
HTTP:

- `request.is_secure` est faux → **le cookie Secure ne part jamais**;
- `url_for(_external=True)` fabrique des liens `http://` (dans les mails!);
- `remote_addr` est le proxy → **tout le monde partage la même limite de débit**.

```python
TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", 0))

if TRUSTED_PROXIES > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXIES, ...)
```

Le **nombre** compte: `x_for=2` alors qu'il n'y a qu'un proxy laisse le client
injecter la valeur qu'il veut dans `X-Forwarded-For`.

### 3. Les en-têtes, dans un `after_request`

Un `after_request` s'applique à **toutes** les réponses, erreurs comprises: c'est
le seul endroit où on est sûr de ne rien oublier.

- `X-Content-Type-Options: nosniff` — pas de « devinette » de type;
- `X-Frame-Options: DENY` — pas de clickjacking;
- `Referrer-Policy` — ne pas fuiter l'URL complète (et ses tokens!) vers l'extérieur;
- `Content-Security-Policy` — défense en profondeur contre le XSS. Volontairement
  large ici (CDN Bootstrap + scripts inline). Une vraie CSP se resserre par
  itérations;
- `Strict-Transport-Security` — **seulement si la réponse est en HTTPS**. La poser
  trop tôt rend le domaine inaccessible si le certificat expire.

### 4. Rotation de session: la session fixation

```python
def login(self, user: UserDTO):
    session.clear()          # <- la rotation
    session['user_id'] = user.user_id
```

L'attaque: un attaquant vous fait utiliser un identifiant de session qu'il
connaît (lien piégé, cookie posé par un sous-domaine). Vous vous connectez… et il
possède maintenant une session **authentifiée**: la vôtre.

La parade est toujours la même: **à l'élévation de privilège, on repart d'une
session vierge**. Flask n'a pas de `regenerate_id()` (sa session vit dans le
cookie signé), mais `session.clear()` a le même effet utile.

À faire aussi lors d'un changement de mot de passe. À l'étape 14, le JWT rend
cette attaque sans objet — il n'y a plus d'identifiant de session réutilisable.

### 5. Le certificat de développement

`HTTPS=True` sert en TLS: soit le certificat de `certs/` (généré par
`certs/generer.sh`), soit un certificat jetable (`ssl_context='adhoc'`). Le
navigateur affiche un avertissement: c'est normal, un certificat auto-signé n'est
garanti par aucune autorité. En production: Let's Encrypt (gratuit, renouvelé
automatiquement par certbot).

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/17-https-et-cookies.md`](docs/17-https-et-cookies.md)

---

## Étape suivante

[`13-waf-modsecurity`](../13-waf-modsecurity/) — mettre un pare-feu applicatif
devant l'application.
