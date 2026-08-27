# Sécurité web pour développeurs — OWASP Top 10:2025

Mémo de survie pour quelqu'un qui **écrit** du code, pas pour quelqu'un qui
attaque. L'objectif n'est pas de savoir exploiter une faille, c'est de savoir
la **reconnaître dans une pull request** et d'avoir le réflexe correct à
portée de main.

Chaque section suit le même plan : *le motif dangereux* → *la correction* →
*le réflexe*. Les exemples sont ceux du labo (`app/lessons/`), en Python/Flask,
mais les motifs sont indépendants du langage.

> Le labo est la version exécutable de ce document : `python run.py`, puis
> <http://127.0.0.1:5000/>. Voir [README.md](README.md) pour le démarrage.

---

## Les sept réflexes

Si vous ne retenez que ça :

1. **Ne jamais construire du code avec des données.** SQL, HTML, shell, LDAP,
   XPath : un mécanisme de paramétrage, jamais de la concaténation.
2. **Valider en entrée, échapper en sortie.** La validation dit « cette donnée
   est acceptable » ; l'échappement dépend du contexte de destination.
3. **Autoriser à chaque accès, côté serveur.** Un identifiant dans l'URL n'est
   pas une autorisation ; un cookie applicatif n'est pas une identité.
4. **Sécurisé par défaut.** La protection est globale (`before_request`,
   décorateur, middleware) et l'exception est explicite — jamais l'inverse.
5. **Refuser par défaut (liste blanche).** On énumère ce qui est permis, pas ce
   qui est interdit.
6. **Supposer que ça arrivera.** Journaux exploitables, secrets cloisonnés,
   dépendances à jour : c'est ce qui limite les dégâts.
7. **Échouer en fermé, et d'un seul bloc.** Une vérification qui ne peut pas
   conclure répond « non ». Une opération interrompue est annulée entièrement.

---

## A01 — Contrôle d'accès cassé

La faille la plus courante et la moins détectable par outil : elle ne se voit
que si on connaît l'intention du code. Depuis 2025, cette catégorie **absorbe
le SSRF**.

### IDOR — l'identifiant n'est pas une autorisation

```python
# ❌ l'objet est chargé depuis un id fourni par le client
invoice_id = request.args.get("id", type=int)
invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()

# ✅ le propriétaire fait partie du filtre : impossible de l'oublier après coup
invoice = db.execute(
    "SELECT * FROM invoices WHERE id = ? AND owner_id = ?",
    (invoice_id, current_user()["id"]),
).fetchone()
if invoice is None:
    abort(404)   # même réponse pour « n'existe pas » et « pas à vous »
```

Mettre l'autorisation **dans le filtre** plutôt que dans un `if` après le
chargement : un `if` s'oublie au prochain remaniement, un `WHERE` non.

Les UUID ne corrigent rien. Ils rendent l'énumération plus lente, c'est tout —
l'URL fuite par le presse-papier, les logs, le `Referer`, un partage.

### Autorisation manquante — « personne ne connaît cette URL »

```python
# ❌ sécurité par l'obscurité : la page n'est pas dans le menu, donc invisible…
@bp.get("/console-secrete-x7")
@login_required
def admin_vulnerable(): ...

# ✅ rôle relu en base à chaque requête
@bp.get("/console")
@role_required("admin")
def admin_secure(): ...
```

Le rôle vient de la base, jamais d'un champ du formulaire, d'un cookie
applicatif ou d'un claim non vérifié. **Cacher un bouton dans l'interface n'est
pas un contrôle d'accès** : l'API est appelable directement.

### CSRF — le navigateur de la victime agit à sa place

Une page tierce poste un formulaire vers votre application ; le navigateur y
joint le cookie de session. Sans jeton, la requête est indistinguable d'une
vraie.

```python
# ✅ une seule fois, pour toute l'application (app/__init__.py)
@app.before_request
def protect_against_csrf():
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return None
    submitted = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not csrf_is_valid(submitted):
        return render_template("csrf_rejected.html"), 400
```

```python
# app/security.py — comparaison à temps constant, réflexe pour tout secret
return hmac.compare_digest(expected, submitted)
```

Plus `SESSION_COOKIE_SAMESITE = "Lax"` comme deuxième ligne de défense. En
pratique : `Flask-WTF` (`CSRFProtect(app)`) fait tout ça pour vous.

⚠ Corollaire : **un `GET` ne doit jamais modifier l'état**. Un `GET
/supprimer/42` contourne toute protection CSRF basée sur les méthodes.

### SSRF — le serveur va chercher une URL fournie par le client

Le serveur devient un relais vers le réseau interne, avec son adresse IP et ses
droits (métadonnées cloud, base de données, back-office).

```python
# ❌ le serveur récupère ce qu'on lui demande
body = requests.get(request.form["url"]).text

# ✅ liste blanche de schémas ET d'hôtes, validée avant l'appel
parsed = urlparse(url)
if parsed.scheme not in {"https"} or parsed.hostname not in ALLOWED_HOSTS:
    abort(400)
```

À prévoir en plus : `allow_redirects=False` (une redirection revalide tout),
timeout court, taille de réponse plafonnée, et idéalement un proxy sortant
isolé du réseau interne. Filtrer les IP privées « à la main » ne suffit pas :
DNS rebinding, IPv6, notations décimales, `[::ffff:127.0.0.1]`.

---

## A02 — Mauvaise configuration de sécurité

Passée 5ᵉ → 2ᵉ en 2025. Tout se joue **avant la première ligne de métier**, et
une mauvaise configuration ne produit aucun symptôme visible.

```python
class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]      # jamais dans le code
    SESSION_COOKIE_HTTPONLY = True             # hors de portée de JavaScript
    SESSION_COOKIE_SAMESITE = "Lax"            # défense de base contre le CSRF
    SESSION_COOKIE_SECURE = True               # HTTPS obligatoire (production)
    PERMANENT_SESSION_LIFETIME = 1800
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024       # déni de service trivial
```

En-têtes de réponse, posés une fois pour toutes (`after_request`) :

```python
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; "
        "form-action 'self'; object-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",  # HTTPS seulement
}
```

Les deux qui coûtent le plus cher quand ils manquent :

- **`debug=True` en production** — le débogueur Werkzeug est une console Python
  à distance. Ce n'est pas « une fuite d'information », c'est une prise de
  contrôle du serveur. Même sans le débogueur, la page d'erreur affiche la
  trace, le code source et les **variables locales** : jetons, clés d'API,
  requêtes SQL.
- **`SECRET_KEY` en dur** — qui connaît la clé fabrique le cookie de session de
  son choix. Pas besoin du mot de passe de qui que ce soit :

  ```python
  serializer = app.session_interface.get_signing_serializer(app)
  cookie = serializer.dumps({"user_id": 3})   # 3 = admin. Voilà.
  ```

  Corollaire : une clé compromise se **change**, et la rotation invalide toutes
  les sessions — c'est le comportement voulu.

Le réflexe qui tient dans le temps : **un test automatisé** sur la
configuration. Dix lignes, et c'est le seul filet qui survit à trois ans de
remaniements.

```python
def test_configuration_de_production(client):
    assert client.application.config["DEBUG"] is False
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in r.headers
```

---

## A03 — Chaîne d'approvisionnement logicielle

Nouvelle catégorie 2025 : elle élargit « composants vulnérables » à **tout ce
qui entre dans l'artefact livré** — paquets, miroirs, images de base, actions
de CI, scripts de build, extensions d'IDE, générateurs de code.

Lecture critique d'un `requirements.txt` :

```
Flask                       # ❌ non épinglé : deux installs = deux applications
reqeusts==2.31.0            # ❌ typosquat de `requests` — pip exécute le paquet
colourama>=0.4              # ❌ typosquat + borne ouverte
PyYAML==5.3.1               # ⚠ épinglé sur une version connue vulnérable
cryptography==*             # ❌ joker : accepte toute publication future
git+https://github.com/inconnu/utils.git@main   # ❌ le contenu change sans la ligne
python-dateutil==2.9.0.post0 \
    --hash=sha256:a8b2bc…   # ✅ épinglé ET vérifiable par empreinte
```

| Maillon | Ce qui arrive | Ce qu'on fait |
|---|---|---|
| Poste de dev | Extension d'IDE, script `postinstall`, `curl … \| sh` | Revue des extensions, secrets hors du poste |
| Résolution | Typosquatting, **confusion de dépendances** (un paquet interne repris sur PyPI public), compte de mainteneur repris | Lockfile + empreintes, miroir interne **sans repli public**, quarantaine des versions récentes |
| Build / CI | Action non épinglée (`@v4`), image `:latest`, jeton de CI avec droits d'écriture | Épingler au **SHA**, droits minimaux par job, provenance/SLSA |
| Livraison | Artefact modifié entre build et déploiement | Signature vérifiée (cosign/Sigstore), SBOM archivé |
| Exécution | Dépendance qui télécharge du code au démarrage, script CDN sans SRI | Sortie réseau restreinte, `integrity=`, auto-hébergement |

```bash
pip-audit                                    # compare l'environnement à la base OSV
pip install -r requirements.txt --require-hashes
```

Et pour un script tiers dans une page :

```html
<script src="https://cdn.exemple/lib.js"
        integrity="sha384-…" crossorigin="anonymous"></script>
```

Le point aveugle habituel : les **dépendances transitives**. C'est le lockfile
qui les fige, pas le `requirements.txt`.

---

## A04 — Défaillances cryptographiques

```python
# ❌ mot de passe en clair : une lecture de la base, et c'est fini
# ❌ MD5/SHA-1/SHA-256 « nu » : rapide à calculer donc rapide à casser,
#    et identique pour deux utilisateurs ayant le même mot de passe
hashlib.md5(password.encode()).hexdigest()

# ✅ hash lent + sel aléatoire par utilisateur
from werkzeug.security import generate_password_hash, check_password_hash
stored = generate_password_hash(password)          # scrypt/pbkdf2 par défaut
check_password_hash(stored, password)              # → bool
```

Deux hachages du **même** mot de passe donnent deux empreintes différentes :
c'est le sel. Les tables arc-en-ciel ne servent plus à rien, chaque mot de
passe doit être attaqué séparément.

Le reste du sujet, plus souvent en cause que l'algorithme lui-même :

- **Ne jamais inventer de crypto.** Bibliothèque éprouvée, mode authentifié
  (AES-GCM, `cryptography.fernet`), jamais ECB, jamais un IV réutilisé.
- **`secrets`, pas `random`** pour tout ce qui doit être imprévisible
  (`random` est un générateur déterministe, prédictible).
- **Comparer les secrets avec `hmac.compare_digest`** (`==` fuit par le temps).
- **HTTPS partout**, HSTS, redirection systématique, cookies `Secure`.
- **Données au repos** : ce qu'on ne stocke pas ne fuite pas. Un numéro de
  carte complet, un numéro de sécurité sociale, une date de naissance — la
  meilleure protection est de ne pas les avoir.

---

## A05 — Injection

### SQL

```python
# ❌ la saisie devient du code
sql = f"SELECT * FROM products WHERE name LIKE '%{q}%'"

# ✅ requête paramétrée : la valeur reste une valeur, jamais du code
db.execute("SELECT * FROM products WHERE name LIKE ?", (f"%{q}%",))
```

Un `ORDER BY` ne peut **pas** être paramétré (c'est un identifiant, pas une
valeur) → liste blanche obligatoire :

```python
SORTABLE = {"name": "name", "price": "price", "stock": "stock"}
column = SORTABLE.get(request.args.get("sort"), "name")
sql = f"SELECT … ORDER BY {column}"     # sûr : `column` ne vient plus du client
```

Le cas qui marque les esprits, à montrer une fois à toute l'équipe : dans

```python
sql = f"SELECT id, role FROM users WHERE username = '{u}' AND password = '{p}'"
```

saisir `admin' --` comme identifiant commente la vérification du mot de passe.
Le code applicatif, lui, fait ce qu'il a toujours fait — « une ligne renvoyée =
connexion » — et ouvre une **vraie session admin**. Prise de contrôle complète,
sans jamais connaître le mot de passe.

Un ORM protège des injections tant qu'on ne lui passe pas de SQL brut
(`text()`, `.extra()`, `raw()`).

### XSS

```jinja
{# ❌ le script stocké dans le commentaire s'exécute #}
{{ comment.body|safe }}

{# ✅ échappement par défaut de Jinja : ne rien faire, c'est la bonne réponse #}
{{ comment.body }}

{# ✅ HTML riche indispensable : liste blanche de balises et d'attributs #}
{{ sanitize_html(comment.body) }}
```

- On stocke la donnée **brute** ; c'est l'**affichage** qui échappe. La même
  donnée part en HTML, en JSON, dans un attribut, dans un e-mail — les règles
  d'échappement ne sont pas les mêmes.
- Assainir : **liste blanche** (`nh3`, `bleach`), jamais liste noire. Filtrer
  `<script>` ne sert à rien face à `<img src=x onerror=…>`.
- Attention aux `href` : `javascript:`, `data:` sont des schémas exécutables.
- Côté navigateur, `innerHTML` = `|safe`. Utiliser `textContent`.
- La **CSP** est le filet : même avec une faille d'échappement, `script-src
  'self'` bloque le script inline. Elle ne remplace pas l'échappement.
- `HttpOnly` limite l'impact : une XSS ne peut plus voler le cookie de session.
  Elle peut toujours agir **à travers** la session de la victime.

### Les autres injections, même motif

`subprocess` avec `shell=True`, `eval`, `os.system`, en-têtes SMTP, LDAP,
XPath, et les chemins de fichiers :

```python
# ❌ path traversal : "../../etc/passwd"
open(os.path.join(BASE, request.args["fichier"]))

# ✅ on résout, puis on vérifie qu'on est resté dans le dossier
chemin = (BASE / request.args["fichier"]).resolve()
if not chemin.is_relative_to(BASE.resolve()):
    abort(400)
```

---

## A06 — Conception non sécurisée

Ici le code est **correct** : pas d'injection, pas de XSS. La faille est dans
le parcours lui-même, et aucun analyseur statique ne la trouvera.

Exemple canonique, le « mot de passe oublié » :

```python
# ❌ code à 4 chiffres, sans expiration, réutilisable, vérifiable en boucle
code = f"{secrets.randbelow(10000):04d}"      # 10 000 possibilités = quelques secondes

# ✅ jeton signé, lié au compte, à durée de vie courte, à usage unique
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

token = URLSafeTimedSerializer(SECRET_KEY, salt="reset-mot-de-passe").dumps({"uid": user_id})
data = serializer.loads(token, max_age=900)   # lève si expiré ou modifié
```

Les réflexes de conception, qui se décident **avant** d'écrire le code :

- **Pas d'énumération de comptes.** « Si ce compte existe, un lien vient d'être
  envoyé » — réponse identique, et temps de réponse comparable, que le compte
  existe ou non. Vaut aussi pour l'inscription et le formulaire de connexion.
- **Usage unique et expiration** pour tout jeton (réinitialisation, invitation,
  validation d'e-mail, lien de partage).
- **Limiter le nombre d'essais** partout où il y a un secret à deviner.
- **Modéliser les abus, pas seulement les fonctionnalités** : « et si
  l'utilisateur envoie ça 10 000 fois ? », « et si c'est son propre compte
  qu'il vise ? », « et s'il change le prix dans le formulaire ? ».
- **Les règles métier se vérifient côté serveur.** Le prix, la remise, le
  quota, le total : ce qui vient du formulaire est une suggestion.

---

## A07 — Défaillances d'authentification

```python
# ❌ aucune limitation : le nombre d'essais n'est borné que par le débit réseau
for candidate in COMMON_PASSWORDS:
    if check_password_hash(user["password_hash"], candidate): ...

# ✅ compteur persistant + verrouillage temporaire + message unique
if user["locked_until"] and datetime.fromisoformat(user["locked_until"]) > now:
    return "Compte temporairement verrouillé."
...
attempts = user["failed_logins"] + 1
lock = now + timedelta(minutes=15) if attempts >= 5 else None
```

```python
# ❌ identité lue dans un cookie applicatif : le client contrôle la valeur
is_admin = request.cookies.get("demo_identity", "").endswith("role=admin")

# ✅ session signée par le serveur, rôle relu en base
user = current_user()      # session["user_id"] → SELECT … FROM users
```

À ajouter dans une vraie application :

- **Limitation par IP** en amont (reverse proxy, `Flask-Limiter`) : le
  verrouillage par compte ne protège pas du *credential stuffing*, qui essaie
  un mot de passe sur des milliers de comptes.
- **Second facteur** pour les comptes sensibles ; c'est ce qui rend le vol de
  mot de passe non exploitable.
- **`session.clear()` à la connexion** (fixation de session) et à la
  déconnexion, côté serveur.
- **Longueur plutôt que complexité** : ≥ 12 caractères, et un contrôle contre
  une liste de mots de passe déjà compromis (HIBP). Les règles
  « majuscule + chiffre + symbole » produisent `Password1!`.
- **Réauthentification** avant les actions critiques (changement d'e-mail, de
  mot de passe, suppression de compte).

---

## A08 — Défaut d'intégrité (données et logiciels)

```python
# ❌ `pickle` ne décrit pas des données, il décrit COMMENT reconstruire un
#    objet — donc quels appels effectuer. Désérialiser = exécuter.
data = pickle.loads(base64.b64decode(request.form["blob"]))

# ✅ format inerte + validation stricte des champs attendus
data = json.loads(raw)
if not isinstance(data, dict):
    abort(400)
for field, expected_type in {"produit": str, "quantite": int}.items():
    if field not in data or not isinstance(data[field], expected_type):
        abort(400)
if not 1 <= data["quantite"] <= 100:
    abort(400)
```

Même famille : `yaml.load` (utiliser `yaml.safe_load`), `marshal`, `shelve`,
les désérialiseurs Java/PHP, et les fichiers de configuration exécutables.

Deux compléments :

- **Valider les types ET les bornes**, et refuser les champs inattendus. Un
  `dict` JSON versé tel quel dans un objet métier, c'est du *mass assignment* :
  `{"quantite": 1, "role": "admin"}`.
- **Intégrité des mises à jour** : vérifier la signature d'un artefact avant de
  l'exécuter, `integrity=` sur les scripts tiers, ne pas faire confiance à un
  webhook non signé (comparer la signature avec `hmac.compare_digest`).

---

## A09 — Journalisation & alerting

```python
# ❌ deux erreurs : on journalise le mot de passe, et on concatène des données
#    utilisateur brutes — un retour à la ligne forge une fausse entrée
log.info(f"Tentative de connexion user={username} password={password}")

# ✅ journal structuré : événement nommé, secrets masqués, CR/LF neutralisés
def log_good(event, **fields):
    safe = {}
    for key, value in fields.items():
        if any(s in key.lower() for s in ("password", "token", "secret", "cvv")):
            safe[key] = "[masqué]"
        else:
            safe[key] = re.sub(r"[\r\n\t]", " ", str(value))[:120]
    logger.info('event="%s" %s', event, " ".join(f'{k}="{v}"' for k, v in safe.items()))
```

Ce qui doit **toujours** être journalisé :

- échec d'authentification (compte, IP, horodatage) ;
- verrouillage de compte, changement de mot de passe ou d'e-mail ;
- refus d'autorisation (403), surtout répétés ;
- rejet de jeton CSRF, vague d'erreurs de validation ;
- actions d'administration : création de compte, changement de rôle.

Ce qui ne doit **jamais** y figurer : mots de passe, jetons, cookies de
session, numéros de carte, contenu de messages privés, et plus largement tout
ce que le RGPD vous obligerait à effacer plus tard. Un log est copié, agrégé,
envoyé à un tiers, conservé un an.

Et le point qui fait toute la différence : **un journal que personne ne regarde
ne sert à rien.** Le livrable n'est pas le log, c'est le seuil d'alerte : « 50
403 en une minute pour un même compte → notification ». Prévoyez aussi une
rétention suffisante — le délai moyen de détection d'une intrusion se compte en
mois, pas en jours.

---

## A10 — Mauvaise gestion des conditions exceptionnelles

Nouvelle catégorie 2025. Le code est correct **sur le chemin nominal** ; la
faille n'apparaît que le jour où quelque chose casse — c'est-à-dire le jour où
quelqu'un le provoque.

### Fail open

```python
# ❌ la branche d'erreur est PLUS permissive que la branche normale
try:
    return serializer.loads(token, max_age=900)["premium"] is True
except Exception:
    return True          # « si le service tombe, on ne bloque pas les clients »
```

Résultat : il suffit d'envoyer un jeton **cassé** pour obtenir l'accès. Pas
besoin d'en fabriquer un valide.

```python
# ✅ exceptions attrapées une par une, refus par défaut, et rien de supposé
try:
    data = serializer.loads(token, max_age=900)
except SignatureExpired:
    log("entitlement.expired");       return False
except BadSignature:
    log("entitlement.bad_signature"); return False
return isinstance(data, dict) and data.get("premium") is True
```

### Opération à moitié appliquée

```python
# ❌ deux commits séparés : le débit est validé, le crédit n'a jamais lieu,
#    et l'exception est avalée. L'argent disparaît de la base.
db.execute("UPDATE accounts SET balance = balance - ? WHERE id = 1", (amount,))
db.commit()
try:
    fraud_check(amount)
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = 2", (amount,))
    db.commit()
except FraudCheckFailed:
    return "Opération refusée."      # message rassurant, base incohérente

# ✅ validation des cas limites AVANT, puis une seule transaction
amount = parse_montant(raw)          # non numérique, négatif, > solde → refus net
try:
    with db:                          # validée à la sortie, annulée si ça lève
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = 1", (amount,))
        fraud_check(amount)
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = 2", (amount,))
except FraudCheckFailed as exc:
    log_good("transfer.rejected", reason=str(exc), amount=amount)
    return "Opération refusée."      # cette fois, c'est vrai
```

Les réflexes :

- `except Exception:` / `except:` autour d'un **contrôle** → question
  systématique en revue : *la branche d'erreur est-elle plus permissive ?*
- `try/except/pass` → une erreur silencieuse est une faille en attente.
- Deux `commit()` dans la même opération métier → une transaction.
- Un montant négatif inverse un virement ; un `0` divise ; une chaîne vide
  passe les tests. **Les cas limites se valident explicitement**, ils ne se
  laissent pas remonter en 500.
- Une page d'erreur générique pour le client, le détail dans les journaux.

---

## Ce que le Top 10 ne dit pas explicitement

Motifs fréquents en revue, rattachés à une catégorie mais faciles à manquer :

| Motif | Le risque | Le réflexe |
|---|---|---|
| **Mass assignment** | `User(**request.form)` → `role=admin` | Liste blanche de champs modifiables |
| **Open redirect** | `redirect(request.args["next"])` → hameçonnage crédible | N'accepter qu'un chemin relatif, jamais un hôte |
| **Upload de fichiers** | Exécution, écrasement, saturation du disque | Type vérifié par le contenu, nom regénéré, hors racine web, taille plafonnée |
| **CORS permissif** | `Access-Control-Allow-Origin: *` + credentials | Liste d'origines explicite, jamais `*` avec cookies |
| **Absence de rate limiting** | Force brute, scraping, coût cloud | Limite par IP **et** par compte, sur les routes coûteuses |
| **JWT mal validé** | `alg: none`, signature non vérifiée, pas d'expiration | Algorithme imposé, `exp` vérifié, révocation prévue — ou juste une session serveur |
| **Secrets dans le dépôt** | Clé publiée pour toujours (l'historique Git garde tout) | Variables d'environnement / coffre, `gitleaks` en CI, **rotation** après fuite |
| **Race condition** | Double utilisation d'un coupon, double retrait | `SELECT … FOR UPDATE`, contrainte d'unicité, idempotence |
| **Erreurs bavardes** | Trace SQL, version, chemins renvoyés au client | Message générique côté client, détail en log |

---

## Checklist avant mise en production

- [ ] `DEBUG = False`, débogueur inaccessible, page d'erreur générique
- [ ] `SECRET_KEY` depuis l'environnement, différente par environnement
- [ ] HTTPS forcé, HSTS, cookies `Secure` + `HttpOnly` + `SameSite`
- [ ] En-têtes de sécurité vérifiés **par un test**, pas à l'œil
- [ ] Protection CSRF globale sur toutes les méthodes non idempotentes
- [ ] Mots de passe en hash lent salé, limitation des essais
- [ ] Autorisation testée : un utilisateur A ne peut pas lire les données de B
- [ ] Dépendances épinglées, `pip-audit` vert, lockfile commité
- [ ] Journaux sans secrets, avec au moins une alerte branchée
- [ ] Sauvegardes **restaurées au moins une fois** pour de vrai
- [ ] Un contact et une procédure connus en cas d'incident

## Grille de revue de code

| Je vois… | Je vérifie… |
|---|---|
| `f"SELECT … {x}"`, `% x`, `+ x` | Requête paramétrée, liste blanche pour les identifiants SQL |
| `\|safe`, `Markup(`, `innerHTML` | Origine de la donnée, assainissement par liste blanche, CSP |
| `request.args["id"]` puis chargement direct | Le filtre inclut-il le propriétaire ? le rôle est-il relu en base ? |
| Un `POST` sans jeton | Protection CSRF globale, cookie `SameSite` |
| `md5`, `sha1`, `sha256` sur un mot de passe | Hash lent salé (`generate_password_hash`, argon2, bcrypt) |
| `pickle`, `yaml.load`, `eval`, `shell=True` | Format inerte (JSON) + validation de schéma |
| Une URL fournie par l'utilisateur et appelée par le serveur | Liste blanche de schémas et d'hôtes, pas de redirection suivie |
| Une clé, un mot de passe ou un jeton dans le dépôt | Environnement / coffre, rotation, `.gitignore` |
| `except Exception:` autour d'un contrôle | La branche d'erreur est-elle plus permissive ? |
| Deux `commit()` dans la même opération métier | Une transaction : que reste-t-il en base si ça casse au milieu ? |
| Une dépendance sans `==`, une action de CI en `@v4`, une image `:latest` | Épinglage (version / SHA), empreintes, index sans repli public |
| `random` pour un jeton, `==` pour un secret | `secrets`, `hmac.compare_digest` |

## Outils à brancher dans la CI

| Outil | Ce qu'il trouve |
|---|---|
| `pip-audit`, Dependabot / Renovate | Dépendances vulnérables (A03) |
| Lockfile + `--require-hashes`, SBOM | Ce qui est réellement déployé (A03) |
| `bandit -r app` | Motifs dangereux en Python (A05, A08), dont `try/except/pass` (A10) |
| `ruff` + revue humaine | Qualité, code mort, incohérences |
| `gitleaks` | Clés commitées (A04) |
| Test des en-têtes et de `DEBUG` | Régression silencieuse de configuration (A02) |
| Tests d'autorisation et d'invariants métier | Contrôle d'accès (A01), opérations à moitié appliquées (A10) |

**Aucun outil ne trouve les failles de conception (A06) ni les contrôles
d'accès manquants (A01).** Ceux-là se voient en revue et en test — c'est
précisément pourquoi ce document existe.

---

## Ce qui a changé depuis l'édition 2021

| 2021 | 2025 | Changement |
|---|---|---|
| A01 Contrôle d'accès | **A01** | Inchangé en tête ; absorbe le SSRF |
| A05 Mauvaise configuration | **A02** | Monte de trois places |
| A06 Composants obsolètes | **A03** | Élargie en « chaîne d'approvisionnement » |
| A02 Cryptographie | **A04** | Descend de deux places |
| A03 Injection | **A05** | Descend de deux places |
| A04 Conception non sécurisée | **A06** | Descend de deux places |
| A07 Identification & authentification | **A07** | Stable, nom raccourci |
| A08 Intégrité | **A08** | Stable |
| A09 Journalisation & supervision | **A09** | Stable, « monitoring » → « alerting » |
| A10 SSRF | **A10** | Remplacée : mauvaise gestion des conditions exceptionnelles |

## Pour aller plus loin

- OWASP Top 10:2025 — <https://owasp.org/Top10/2025/>
- OWASP Cheat Sheet Series (une fiche par sujet) — <https://cheatsheetseries.owasp.org/>
- OWASP ASVS (checklist d'exigences, par niveau) — <https://owasp.org/www-project-application-security-verification-standard/>
- Flask — Security Considerations — <https://flask.palletsprojects.com/en/stable/web-security/>
- Have I Been Pwned (API mots de passe compromis) — <https://haveibeenpwned.com/API/v3>
