# Étape 08 — Mot de passe oublié (et Mailpit)

Dernière fonctionnalité: « j'ai oublié mon mot de passe ». C'est un bon exercice
de fin de formation parce qu'il touche à tout — un service, un formulaire, un
template de mail, un token signé, et quatre pièges de sécurité.

On y ajoute aussi un serveur SMTP de développement (**Mailpit**), et des règles de
mot de passe qui changent selon l'environnement.

---

## Démarrer

```bash
docker compose up -d db-example mailpit      # <- deux services maintenant
pip install -r requirements.txt
./sqlAlchemy.sh -u
python main.py
```

| Adresse | Quoi |
|---|---|
| <http://localhost:8080> | l'application |
| <http://localhost:8025> | **Mailpit**: tous les mails envoyés. Rien ne part réellement. |

Parcours à essayer: `/login` → « Mot de passe oublié ? » → l'adresse
`test@example.com` → ouvrez Mailpit → cliquez le lien → choisissez un nouveau mot
de passe → reconnectez-vous.

Aucune nouvelle dépendance n'a été nécessaire: `smtplib` est dans la bibliothèque
standard, et `itsdangerous` (qui signe les tokens) est déjà installée — c'est elle
qui signe les cookies de session de Flask.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | + le service `mailpit` |
| `.env` | + `MAIL_HOST`, `MAIL_PORT`, `MAIL_FROM`, `MAIL_USE_TLS`, `PASSWORD_RESET_MAX_AGE` |
| `app/services/mail_service.py` | envoi SMTP (stdlib) |
| `app/services/password_reset_service.py` | tokens signés, envoi du lien, réinitialisation |
| `app/services/user_service.py` | + `update_password()` |
| `app/forms/user/user_forgot_password_form.py` | l'adresse email |
| `app/forms/user/user_reset_password_form.py` | le nouveau mot de passe |
| `app/forms/user/user_register_form.py` | règles de mot de passe selon l'environnement |
| `app/controllers/user_controller.py` | `/password/forgot`, `/password/reset/<token>` |
| `app/templates/users/forgot_password.html`, `reset_password.html` | les deux pages |
| `app/templates/emails/password_reset.txt` | le corps du mail |

### 1. Mailpit: un SMTP bouchon

```yaml
  mailpit:
    image: axllent/mailpit:latest
    ports:
      - '1025:1025'   # SMTP: là où l'application dépose ses mails
      - '8025:8025'   # interface web
```

Mailpit accepte tous les mails et **n'en envoie aucun**. C'est la bonne façon de
travailler sur des envois: zéro risque d'écrire à un vrai destinataire, aucun
compte SMTP à configurer, et on relit le contenu exact reçu (en-têtes compris).

`MailService` retourne `False` au lieu de lever si le serveur est absent: un SMTP
en panne ne doit pas transformer la page en erreur 500.

> Si vous lancez l'app **dans** un conteneur, `MAIL_HOST` devient `mailpit` et non
> `127.0.0.1` — même piège que `DATABASE_URL`.

### 2. Le token: aucune table supplémentaire

```python
self.__serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'],
                                           salt='password-reset')

token = self.__serializer.dumps({
    'user_id': user.user_id,
    'fingerprint': self.__fingerprint(user.password),
})
```

Trois protections, à comprendre **ensemble**:

| Protection | Mécanisme | Ce que ça empêche |
|---|---|---|
| Intégrité | signature HMAC (`BadSignature`) | fabriquer un token, ou changer le `user_id` dedans |
| Expiration | horodatage + `max_age` | réutiliser un vieux lien (1 h par défaut) |
| Usage unique | empreinte du hash de mot de passe | rejouer un lien resté dans une boîte mail |

L'usage unique mérite un mot: le token embarque un `sha256` tronqué du hash de
mot de passe **courant**. Dès que le mot de passe change, l'empreinte recalculée
ne correspond plus — usage unique sans rien stocker.

Le `salt` sépare les usages: un token de réinitialisation ne sera jamais accepté là
où on attend un autre type de token signé, même clé secrète.

La comparaison utilise `secrets.compare_digest()` et non `==`: temps constant, elle
ne laisse pas deviner la valeur attendue.

### 3. Ne pas révéler qui a un compte

```python
password_reset_service.send_reset_link(form.email.data)   # retour ignoré

flash("Si un compte existe pour cette adresse, un lien de "
      "réinitialisation vient d'être envoyé.", "info")
```

Le message est **identique** que l'adresse existe ou non — sinon la page devient un
outil pour savoir qui est inscrit. Même raison que le message unique du login
(étape 06). Un compte désactivé ne reçoit rien non plus.

### 4. Le token est revérifié au POST

```python
def reset(self, token: str, new_password: str) -> bool:
    user = self.__find_user_entity(token)      # revérification
    if user is None:
        return False
    return self.__user_service.update_password(user.user_id, new_password) is not None
```

Entre l'affichage du formulaire (GET) et l'envoi (POST), le token a pu expirer ou
être consommé ailleurs. Vérifier seulement à l'affichage serait une faille.

### 5. Des règles de mot de passe selon l'environnement

```python
PASSWORD_VALIDATORS = (
    [DataRequired(), Length(min=4, max=128)]                    # DEBUG
    if app.debug else
    [DataRequired(), Length(min=12, max=128),                   # PRODUCTION
     Regexp(r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', message="...")]
)
```

Une ternaire évaluée **une seule fois**, à l'import du module. En formation on tape
« admin » cinquante fois par jour; en production on veut 12 caractères. Les
`(?=...)` sont des *lookahead*: ils vérifient la présence d'une catégorie de
caractères sans en consommer.

Le formulaire de réinitialisation **importe la même liste**: il serait dommage de
durcir une porte en laissant l'autre ouverte.

---

## Exercices

### 1. Lire le mail

- Ouvrez Mailpit et regardez le message brut (onglet *Source*): expéditeur,
  sujet, corps. D'où vient chaque partie ?
- Le lien est absolu (`http://localhost:8080/...`). Qu'est-ce qui le rend absolu
  dans `password_reset_service.py`, et pourquoi un lien relatif serait inutilisable
  dans un mail ?
- Modifiez `app/templates/emails/password_reset.txt` pour signer d'un autre nom.

### 2. Attaquer le token

Pour chaque tentative, prédisez le résultat **avant** d'essayer:

- changez un caractère à la fin du token dans l'URL;
- prenez un token valide, décodez sa partie centrale (c'est du base64, pas du
  chiffrement: `base64.urlsafe_b64decode`) — que voyez-vous ? Est-ce grave ?
- fabriquez un token avec un autre `user_id` et re-signez-le… sans la
  `SECRET_KEY`;
- utilisez le lien une première fois (réinitialisation réussie), puis **rechargez
  la même URL**;
- mettez `PASSWORD_RESET_MAX_AGE=1` dans `.env.local`, demandez un lien, attendez
  deux secondes, cliquez.

### 3. L'énumération de comptes

- Demandez un lien pour `inconnu@example.com` puis pour `test@example.com`.
  Comparez **exactement** les deux réponses (texte, code HTTP, temps de réponse).
- Modifiez le controller pour afficher « adresse inconnue » quand c'est le cas.
  Puis expliquez, en une phrase, ce qu'un attaquant peut faire de cette
  information. Remettez le code d'origine.

### 4. Les règles de mot de passe

- En `DEBUG=True`, inscrivez-vous avec `abcd`: accepté.
- Passez `DEBUG=False` dans `.env.local`, relancez, réessayez `abcd`, puis
  `motdepasselong`, puis `MotDePasse123`. Expliquez chaque refus.
- Où la même liste de validators est-elle réutilisée ? Pourquoi est-ce important ?

### 5. Vérification d'adresse à l'inscription

C'est le même mécanisme. Implémentez-le:

1. un champ `email_verified` sur `User` (+ migration);
2. un token signé avec un **autre salt** (pourquoi ?) envoyé à l'inscription;
3. une route `/email/verify/<token>`;
4. `@auth_required` refuse la connexion tant que l'adresse n'est pas vérifiée —
   ou laisse entrer avec un bandeau d'avertissement. Discutez le choix.

### 6. SMTP en panne

Mettez `MAIL_PORT=59999` (aucun serveur), demandez un lien.

- La page plante-t-elle ? Où est-ce rattrapé ?
- L'utilisateur voit-il une différence ? Est-ce souhaitable ?
- Que faudrait-il faire en production (file d'attente, réessai, supervision) ?

---

## Pour aller plus loin

- `../09-projet-final/docs/09-authentification.md` (section « Mot de passe oublié »)
- `../09-projet-final/docs/06-formulaires.md` (validators selon l'environnement)
- `../09-projet-final/docs/02-docker-et-configuration.md` (Mailpit, variables)

---

## Exercices

Les exercices de cette étape sont dans [`EXERCICES.md`](EXERCICES.md):
des énoncés guidés, avec critère de réussite et coup de pouce.

---

## Étape suivante

[`09-projet-final`](../09-projet-final/) — le même code, accompagné des 14
chapitres de documentation et du sujet de projet d'équipe.
