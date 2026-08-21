# 15 — Limiter les tentatives de connexion

Fichiers: `app/models/login_attempt.py`, `app/services/login_attempt_service.py`

Sans limite, rien n'empêche d'essayer des mots de passe en boucle. argon2 rend
chaque essai coûteux (~50 ms), mais 50 ms × 24 h = **1,7 million d'essais**. C'est
très suffisant pour trouver « été2024 ».

Ne pas confondre avec la limitation de **débit** (chapitre 16): ce sont deux
protections différentes, et il faut les deux.

| | Tentatives (ce chapitre) | Débit (chapitre 16) |
|---|---|---|
| Compte quoi | les **échecs de connexion** d'un identifiant | les **requêtes** d'une IP |
| Protège | un compte contre la force brute | le serveur contre l'abus |
| Réaction | verrou temporaire (15 min) | réponse `429` + `Retry-After` |
| Contourné par | un attaquant qui change de compte | un attaquant distribué sur mille IP |
| Stockage | table PostgreSQL | mémoire (Redis en production) |

Le premier laisse passer « un essai sur mille comptes », le second laisse passer
« cinq essais par minute pendant un an ». D'où les deux.

## Les règles

```python
MAX_FAILURES = 5        # échecs consécutifs avant le verrou
LOCK_MINUTES = 15       # durée du verrou
RESET_MINUTES = 60      # au-delà, ce n'est plus une série
```

Une connexion réussie efface le compteur. Trois fautes de frappe étalées sur une
semaine ne doivent pas verrouiller un compte, d'où `RESET_MINUTES`.

## Trois décisions à savoir défendre

**1. Une table, pas un dictionnaire.** Un `dict` en mémoire est perdu au
redémarrage (il suffit d'attendre un déploiement), n'est pas partagé entre les
workers (4 workers gunicorn = 4× les essais autorisés) et grossit indéfiniment.
Coût de la table: deux requêtes SQL par tentative de connexion — négligeable à
l'échelle d'un login.

**2. Le verrou est consulté AVANT le mot de passe.**

```python
bloque = login_attempt_service.locked_seconds(form.username.data)

if bloque > 0:
    flash(f"Trop de tentatives. Réessayez dans {max(1, bloque // 60)} minute(s).")
    return render_template('users/login.html', form=form)
```

Un compte bloqué ne doit pas coûter 50 ms d'argon2 au serveur: sinon le verrou
protège le compte, mais pas la machine.

**3. On compte aussi les identifiants qui n'existent pas.** Sinon il suffirait
d'alterner `admin`, `admln`, `admin` pour ne jamais atteindre 5 échecs
consécutifs. Avec normalisation (`strip().lower()`), sans quoi `ADMIN ` contourne
le compteur de `admin`.

## Le compromis du message

Deux exigences qui se contredisent:

- **ne pas renseigner l'attaquant** — le message ne dit pas si le compte existe;
- **ne pas laisser l'utilisateur légitime dans le noir** — il tape le bon mot de
  passe et se fait refuser, il doit comprendre pourquoi.

Compromis retenu: « Trop de tentatives, réessayez dans N minutes », affiché pour un
identifiant existant comme inexistant.

## Le défaut inhérent: le déni de service ciblé

Un attaquant peut échouer 5 fois **volontairement** pour verrouiller votre compte.
C'est inhérent à toute limitation par compte. Les grands services combinent donc:
compteur par compte **et** par IP, ralentissement progressif plutôt que blocage
sec, captcha après N échecs, et 2FA.

## Un piège de portabilité: naïf vs aware

```python
@staticmethod
def en_utc(valeur):
    return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=timezone.utc)
```

Avec `DateTime(timezone=True)`, PostgreSQL rend un datetime **aware**, SQLite un
datetime **naïf**. Les comparer lève `TypeError: can't compare offset-naive and
offset-aware datetimes`. Ce bug est apparu en écrivant ce chapitre, sur la base
SQLite des tests, alors que PostgreSQL ne disait rien.
