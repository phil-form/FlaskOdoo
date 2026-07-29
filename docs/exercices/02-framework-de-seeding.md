# Exercices — Étape 02

Le sujet: l'auto-enregistrement, l'ordre d'exécution, l'idempotence, et une route
qui n'existe qu'en debug.

---

## 1. Vérifier l'automatisme (et le mesurer)

**Objectif** — constater qu'un seeder ne se déclare plus nulle part.

1. Créez `app/seed/tag_seed.py` avec un modèle `Tag` si vous l'avez fait à
   l'étape 01, sinon un seeder qui écrit simplement dans le journal.
2. Rechargez `/seed`.

Puis répondez:

- combien de fichiers avez-vous modifiés cette fois ? (Comparez à l'exercice 6 de
  l'étape 01.)
- quelle ligne de code, exactement, a provoqué l'enregistrement ?
- à quel *moment* est-elle exécutée: à l'import du module, à la première requête,
  ou à l'appel de `/seed` ?

**Critère de réussite** — vous savez montrer la ligne dans `seedable.py` et dire
qui l'appelle.

---

## 2. L'ordre compte

**Objectif** — provoquer, puis résoudre, une dépendance entre seeders.

Écrivez deux seeders:

- `CountrySeed` qui insère trois pays (créez le modèle `Country`);
- `CitySeed` qui insère deux villes rattachées à un pays existant (modèle `City`
  avec une clé étrangère vers `Country`).

Consignes:

1. donnez-leur d'abord le **même** `order` (ou aucun) et nommez les fichiers de
   façon à ce que `city_seed.py` passe en premier (alphabétiquement, c'est déjà
   le cas);
2. observez ce que dit `/seed`;
3. corrigez avec `order`.

**Critère de réussite** — `/seed` liste `CountrySeed` avant `CitySeed`, et la
page ne signale aucune erreur.

<details><summary>Coup de pouce</summary>

`Seedable.seeders()` trie par `order`. Utilisez des multiples de 10 pour pouvoir
insérer un seeder entre deux plus tard.
</details>

---

## 3. Réparer un seeder non idempotent

**Objectif** — comprendre pourquoi un seed doit pouvoir être relancé.

Écrivez volontairement un seeder **non idempotent**:

```python
class BadSeed(Seedable):
    order = 90

    def seed(self):
        db.session.add(User(username="doublon", password="x"))
        db.session.commit()
```

1. Appelez `/seed` deux fois. Que dit la page la deuxième fois ?
2. Quel est le message d'erreur PostgreSQL exact ? (Regardez la console.)
3. Les seeders suivants ont-ils été exécutés malgré l'erreur ? Pourquoi ?
4. Rendez-le idempotent, de **deux** façons différentes: par un test préalable,
   puis en rattrapant l'exception. Laquelle préférez-vous, et pourquoi ?

**Critère de réussite** — dix appels consécutifs à `/seed` ne créent qu'un seul
utilisateur `doublon`, et la page n'affiche aucune erreur.

---

## 4. La route de debug, et son alternative en ligne de commande

**Objectif** — comprendre pourquoi `/seed` disparaît, et savoir seeder sans HTTP.

1. Mettez `DEBUG=False` dans un `.env.local`, relancez, appelez `/seed`:
   vous devez obtenir un **404**.
2. Expliquez par écrit pourquoi 404 et pas 403.
3. Écrivez une commande CLI équivalente, utilisable même hors debug:

```python
# dans app/__init__.py, ou mieux: app/framework/seed/cli.py
@app.cli.command("seed")
def seed_command():
    """Exécute tous les seeders."""
    for seeder in Seedable.seeders():
        ...
```

Elle s'utilise avec `flask seed`.

**Critère de réussite** — `DEBUG=False flask seed` remplit la base, alors que
`/seed` répond 404.

<details><summary>Coup de pouce</summary>

`Seedable.seeders()` est utilisable partout: l'enregistrement dépend de l'import
(`from app.seed import *`), pas du mode debug. Une commande CLI dispose déjà d'un
contexte applicatif.
</details>

---

## 5. Une classe abstraite intermédiaire

**Objectif** — comprendre le test `__isabstractmethod__` de `Seedable`.

Créez une classe intermédiaire qui **n'implémente pas** `seed()`:

```python
class SeedAvecJournal(Seedable):
    """Ajoute un journal, mais ne définit pas seed(): ce n'est pas un seeder."""

    def log(self, message):
        app.logger.debug(f"[{type(self).__name__}] {message}")
```

puis un vrai seeder qui en hérite.

Questions:

- combien de seeders `/seed` liste-t-il ?
- que se passerait-il si `Seedable.__init_subclass__` ne faisait pas ce test ?
  (Essayez: commentez les deux lignes, rechargez.)

**Critère de réussite** — `SeedAvecJournal` n'apparaît jamais dans la liste, son
enfant si.

---

## 6. Faire le ménage: `unseed`

**Objectif** — étendre le framework maison, pas seulement l'utiliser.

Ajoutez à `Seedable` une méthode `unseed()` **facultative** (valeur par défaut:
ne rien faire), et une route `/unseed`, elle aussi réservée au debug, qui
exécute les seeders dans l'ordre **inverse**.

Questions:

- pourquoi l'ordre inverse ?
- que doit faire `Seed` si un seeder n'a pas redéfini `unseed()` ?
- comment éviter de dupliquer le code entre `/seed` et `/unseed` dans la classe
  `Seed` ?

**Critère de réussite** — `/seed`, `/unseed`, `/seed` remet la base dans le même
état qu'un `/seed` seul.
