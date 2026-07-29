# 02 — Docker & configuration

## docker-compose.yml

Deux services:

```yaml
services:
  app:                                   # l'application Python
    image: python:3.13.14-trixie
    command: "bash -c 'pip install -r requirements.txt && python main.py'"
    working_dir: /app
    volumes:
      - ./:/app                          # le code de l'hôte est monté dans le conteneur
    ports:
      - 8080:8080                        # PORT_HOTE:PORT_CONTENEUR

  db-example:                            # PostgreSQL
    image: postgres:18
    env_file: .env.local                 # variables depuis un fichier (git-ignoré)
    environment:                         # ou en dur ici
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: 1234
    ports:
      - '5435:5432'                      # 127.0.0.1:5435 -> 5432 dans le conteneur
    volumes:
      - ./init_db:/init_db
      - app-volume:/var/lib/postgresql/18/docker

volumes:
  app-volume:                            # volume nommé: les données survivent au conteneur
```

Points à retenir:

- **`ports: '5435:5432'`** — le port 5432 est déjà pris si vous avez un
  PostgreSQL local; on publie donc sur 5435. C'est ce port qui doit apparaître
  dans `DATABASE_URL`.
- **volume monté (`./:/app`)** vs **volume nommé (`app-volume`)** — le premier
  partage un dossier de votre machine (le code, modifiable à chaud), le second
  est un espace géré par Docker qui survit à `docker compose down`. Les données
  PostgreSQL vont dans un volume nommé, sinon un `down` effacerait la base.
- **`env_file: .env.local`** — ce fichier est dans `.gitignore`. Si vous ne
  l'avez pas, `docker compose` refuse de démarrer le service: créez-le, même
  vide.

Et un troisième service, **Mailpit**, pour les mails:

```yaml
  mailpit:
    image: axllent/mailpit:latest
    ports:
      - '1025:1025'   # SMTP: là où l'application dépose ses mails
      - '8025:8025'   # interface web: http://localhost:8025
```

Mailpit est un serveur SMTP « bouchon »: il accepte tous les mails et **n'en
envoie aucun**. On les relit dans son interface web. C'est indispensable pour
travailler sur le « mot de passe oublié » sans écrire à de vrais destinataires,
et sans avoir à configurer un compte SMTP. Aucun volume: la boîte est vidée à
chaque redémarrage du conteneur, et c'est très bien ainsi.

Commandes utiles:

```bash
docker compose up -d db-example mailpit   # base + serveur de mails
docker compose up -d db-example     # démarrer seulement la base, en arrière-plan
docker compose logs -f db-example   # suivre les logs
docker compose down                 # arrêter (les données restent dans le volume)
docker compose down -v              # arrêter ET supprimer le volume (base vidée)
```

En développement, on lance en général **la base dans Docker et l'application sur
la machine** (`python main.py`): rechargement instantané, débogueur de l'IDE
utilisable, pas de reconstruction d'image.

> Attention: si vous lancez aussi l'app dans Docker, `127.0.0.1` dans
> `DATABASE_URL` ne désigne plus la base mais le conteneur de l'app lui-même. Il
> faut alors le nom du service: `postgresql://app:1234@db-example:5432/app`.

## .env et .env.local

```
.env         versionné, valeurs par défaut pour tout le monde
.env.local   git-ignoré, écrase le précédent, propre à votre machine
```

Chargés dans `app/__init__.py`:

```python
load_dotenv()                                    # d'abord .env
env_path = Path().cwd() / '.env.local'
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)         # puis .env.local, qui gagne
```

`override=True` est indispensable: sans lui, `python-dotenv` ne remplace pas une
variable déjà définie et `.env.local` serait ignoré.

### Variables utilisées

| Variable | Rôle | Exemple |
|---|---|---|
| `DATABASE_URL` | connexion SQLAlchemy | `postgresql://app:1234@127.0.0.1:5435/app` |
| `DEBUG` | mode debug, route `/seed`, **règles de mot de passe souples** | `True` |
| `SECRET_KEY` | signe les cookies de session, les jetons CSRF **et les tokens de réinitialisation** | chaîne aléatoire |
| `PORT` | port d'écoute du serveur de dev | `8080` |
| `MAIL_HOST` / `MAIL_PORT` | serveur SMTP (Mailpit en dev) | `127.0.0.1` / `1025` |
| `MAIL_FROM` | expéditeur des mails | `no-reply@flaskodoo.local` |
| `MAIL_USE_TLS` / `MAIL_USERNAME` / `MAIL_PASSWORD` | production seulement | `True` / … |
| `PASSWORD_RESET_MAX_AGE` | validité d'un lien de réinitialisation, en secondes | `3600` |

Deux conséquences de `SECRET_KEY` à connaître: la changer déconnecte tout le
monde **et** invalide tous les liens de réinitialisation en circulation.

À propos de `SECRET_KEY`: elle sert à signer les cookies. La changer déconnecte
tout le monde; la divulguer permet de forger des sessions (donc de se faire
passer pour n'importe quel utilisateur). En production, une valeur aléatoire
longue, uniquement dans l'environnement — jamais dans le dépôt.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Le format de DATABASE_URL

```
postgresql://app:1234@127.0.0.1:5435/app
└────┬────┘  └┬┘ └─┬┘  └───┬────┘ └─┬┘ └┬┘
  driver     user  mdp     hôte    port  base
```

Le driver `postgresql://` implique le paquet `psycopg2-binary`
(dans `requirements.txt`). Sans lui: `ModuleNotFoundError: No module named
'psycopg2'`.

## Le mode debug

```python
app.debug = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")
```

Pourquoi cette comparaison verbeuse? Parce qu'une variable d'environnement est
**toujours une chaîne**: `bool(os.environ.get("DEBUG"))` vaut `True` même pour
`DEBUG=False` (une chaîne non vide est truthy). C'est un piège classique.

Le debug active:

- le rechargement automatique du code,
- les pages d'erreur détaillées **avec une console Python interactive**,
- la Debug Toolbar,
- la route `/seed`.

La console interactive exécute du code arbitraire sur le serveur: `DEBUG=True`
en production est une porte ouverte. C'est aussi pour cette raison que `/seed`
est conditionnée au debug plutôt qu'à un mot de passe.
