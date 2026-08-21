# Étape 10 — Limiter les tentatives de connexion

Deuxième bloc de la formation: **durcir** une application qui marche. Rien de
nouveau côté fonctionnalités, tout côté résistance aux abus.

L'étape 06 laissait un trou: on peut essayer des mots de passe en boucle. argon2
rend chaque essai coûteux (~50 ms), mais 50 ms × 24 h = 1,7 million d'essais. Très
suffisant pour trouver `été2024`.

---

## Démarrer

```bash
docker compose up -d db-example mailpit
pip install -r requirements.txt
./sqlAlchemy.sh -u          # + la table login_attempts
python main.py
```

Essayez de vous connecter 5 fois avec un mauvais mot de passe, puis avec le bon.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/models/login_attempt.py` | **nouveau** — un compteur par identifiant |
| `app/services/login_attempt_service.py` | **nouveau** — verrou, compteur, remise à zéro |
| `app/controllers/user_controller.py` | le verrou est consulté avant toute vérification |
| `migrations/versions/*_limiteur_de_tentatives_*.py` | la table |
| `.env` | `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_MINUTES`, `LOGIN_RESET_MINUTES` |

### 1. Une table, pas un dictionnaire

C'est le premier réflexe: un `dict` en mémoire. Trois problèmes:

- il est **perdu au redémarrage** — il suffit d'attendre un déploiement;
- il n'est **pas partagé entre processus** — 4 workers gunicorn = 4× les essais;
- il **grossit indéfiniment**.

Une table règle les trois, au prix de deux requêtes par tentative de connexion.
À l'échelle d'un login, c'est négligeable.

### 2. Le verrou est consulté AVANT le mot de passe

```python
bloque = login_attempt_service.locked_seconds(form.username.data)

if bloque > 0:
    flash(f"Trop de tentatives. Réessayez dans {max(1, bloque // 60)} minute(s).")
    return render_template('users/login.html', form=form)

user = user_service.login(form)
```

Un compte bloqué ne doit pas coûter un hachage argon2 au serveur: sinon le verrou
protège le compte mais pas la machine.

### 3. On compte aussi les identifiants qui n'existent pas

```python
if user is None:
    login_attempt_service.record_failure(form.username.data)
```

Sinon il suffirait d'alterner `admin`, `admln`, `admin` pour ne jamais être
bloqué. La normalisation (`strip().lower()`) évite le même contournement avec
`ADMIN` ou `admin ` — c'est testé.

### 4. Le compromis du message

Deux exigences qui se contredisent:

- **ne pas renseigner l'attaquant** — le message ne dit pas si le compte existe;
- **ne pas laisser l'utilisateur légitime dans le noir** — il tape le bon mot de
  passe et il est refusé, il DOIT savoir pourquoi.

Compromis retenu: « Trop de tentatives, réessayez dans N minutes », affiché pour
un identifiant existant comme inexistant.

### 5. Le défaut connu: le déni de service ciblé

Un attaquant peut échouer 5 fois volontairement pour **vous** verrouiller. C'est
inhérent à l'approche par compte, et c'est pourquoi les gros services combinent:
compteur par compte **et** par IP (étape 11), captcha après N échecs, et 2FA.

### 6. Un piège de portabilité: naïf vs aware

```python
@staticmethod
def en_utc(valeur):
    return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=timezone.utc)
```

Avec `DateTime(timezone=True)`, PostgreSQL rend un datetime **aware**, SQLite un
datetime **naïf** — les comparer lève `TypeError: can't compare offset-naive and
offset-aware datetimes`. Ce bug est arrivé en écrivant cette étape, sur la base
SQLite des tests, alors que PostgreSQL ne disait rien.

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/15-limitation-des-tentatives.md`](docs/15-limitation-des-tentatives.md)

---

## Étape suivante

[`11-limiteur-de-requetes`](../11-limiteur-de-requetes/) — limiter le débit, cette
fois par IP et sur toutes les routes.
