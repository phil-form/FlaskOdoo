# 17 — HTTPS, cookies et en-têtes

Fichiers: `app/__init__.py`, `main.py`, `certs/generer.sh`

Toutes les protections des chapitres précédents reposent sur un cookie. S'il
voyage en clair ou si le JavaScript peut le lire, elles ne valent rien.

## Les attributs du cookie

```python
SESSION_COOKIE_HTTPONLY=True,
SESSION_COOKIE_SECURE=not app.debug,
SESSION_COOKIE_SAMESITE='Lax',
PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
```

| Attribut | Ce qu'il empêche |
|---|---|
| `HttpOnly` | qu'un XSS **vole** le cookie |
| `Secure` | qu'il parte en clair (une seule requête HTTP suffit à le fuiter) |
| `SameSite=Lax` | qu'il soit envoyé sur un POST venu d'un autre site |
| `PERMANENT_SESSION_LIFETIME` | qu'une session traîne indéfiniment |

`Secure` est conditionné à `app.debug` — sinon plus aucune session sur
`http://localhost`. `Strict` casserait les liens entrants: `Lax` est le bon défaut.

## ProxyFix: sans lui, le durcissement tombe

En production, Flask ne termine pas le TLS: un reverse proxy le fait et parle en
HTTP clair à l'application. Sans `ProxyFix`:

- `request.is_secure` est faux → **le cookie `Secure` ne part jamais**;
- `url_for(_external=True)` fabrique des liens `http://` (dans les mails!);
- `remote_addr` est le proxy → **la limite de débit devient globale**.

```python
if TRUSTED_PROXIES > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXIES, x_proto=..., ...)
```

Le **nombre** doit être exact: `x_for=2` avec un seul proxy laisse le client
injecter la valeur qu'il veut dans `X-Forwarded-For`.

## Les en-têtes, dans un `after_request`

Un `after_request` couvre **toutes** les réponses, erreurs comprises.

| En-tête | Rôle |
|---|---|
| `X-Content-Type-Options: nosniff` | pas de devinette de type MIME |
| `X-Frame-Options: DENY` | pas de clickjacking |
| `Referrer-Policy` | ne pas fuiter l'URL (et ses tokens) vers l'extérieur |
| `Content-Security-Policy` | défense en profondeur contre le XSS |
| `Strict-Transport-Security` | « plus jamais de HTTP », **seulement si déjà en HTTPS** |

La CSP du projet est volontairement large (`'unsafe-inline'`, CDN Bootstrap): une
CSP utile se construit en resserrant par itérations, avec des nonces et des
scripts externalisés. Posée trop strictement d'un coup, elle casse le site; posée
trop large, elle ne protège rien — c'est le seul en-tête qui demande du travail.

HSTS est le plus dangereux: le poser avant que le HTTPS soit stable rend le
domaine inaccessible si le certificat expire.

## Rotation de session

```python
def login(self, user):
    session.clear()          # <- la rotation
    session['user_id'] = user.user_id
```

Contre la **session fixation**: un attaquant vous fait utiliser un identifiant de
session qu'il connaît, vous vous connectez, il possède une session authentifiée.
La règle: **à l'élévation de privilège, session vierge**. À faire aussi au
changement de mot de passe.

Flask n'a pas de `regenerate_id()` (sa session vit dans le cookie signé), mais
`session.clear()` a le même effet utile. Avec un JWT (chapitre 18), l'attaque
devient sans objet.

## HTTPS en développement

`HTTPS=True` sert en TLS avec le certificat de `certs/` (généré par
`certs/generer.sh`) ou un certificat jetable (`ssl_context='adhoc'`, paquet
`cryptography`). Le navigateur avertit: un certificat auto-signé n'est garanti par
aucune autorité. En production: Let's Encrypt, renouvelé par certbot.
