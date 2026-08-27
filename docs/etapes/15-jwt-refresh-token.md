# Étape 15 — JWT avec refresh token

L'étape 14 laissait un dilemme: un access token long est dangereux (on ne peut pas
le révoquer), un access token court est insupportable (reconnexion toutes les 15
minutes).

La paire **access + refresh** règle les deux: un token court et sans état pour
autoriser, un token long et **révocable** pour renouveler.

---

## Démarrer

```bash
docker compose up -d db-example mailpit
pip install -r requirements.txt
./sqlAlchemy.sh -u          # + la table refresh_tokens
python main.py
```

Connectez-vous: deux cookies (`access_token`, 15 min; `refresh_token`, 7 jours).
Naviguez pendant plus de 15 minutes sans jamais vous reconnecter.

---

## Ce qui change

| Fichier | Rôle |
|---|---|
| `app/models/refresh_token.py` | **nouveau** — les tokens révocables, en base |
| `app/services/refresh_token_service.py` | **nouveau** — émission, rotation, révocation |
| `app/services/auth_service_jwt.py` | renouvellement silencieux, deux cookies |
| `app/services/password_reset_service.py` | changer son mot de passe **déconnecte partout** |
| `migrations/versions/*_refresh_tokens.py` | la table |
| `.env` | `JWT_ACCESS_MINUTES=15`, `JWT_REFRESH_DAYS=7` |

### 1. Deux tokens, deux rôles

| | Access token | Refresh token |
|---|---|---|
| Durée | 15 minutes | 7 jours |
| Forme | JWT signé | 32 octets aléatoires (`secrets.token_urlsafe`) |
| Stocké côté serveur | non | **oui, haché** |
| Vérification | signature, puis relecture du compte en base | une requête, révocable |
| Sert à | autoriser chaque requête | obtenir un nouvel access token |
| `SameSite` | `Lax` | `Strict` (il ne sert que sur notre site) |

Le refresh token n'est **pas** un JWT: il n'a rien à transporter, il sert juste de
preuve. Et il est stocké **haché** (sha256), comme un mot de passe: une fuite de
la table ne donne aucune session utilisable.

### 2. Renouvellement silencieux

```python
claims = self.decode(token) if token else None

if claims is None:
    claims = self.__renouveler()      # access expiré -> on tente le refresh
```

L'utilisateur ne voit rien: il ne sait même pas que son access token vivait
quinze minutes.

À noter, parce que la première version de cette étape disait le contraire: ce
n'est **pas** ici que se joue la fraîcheur des droits. Depuis l'étape 14,
`get_current_user()` relit le compte et ses rôles en base à **chaque** requête —
le token n'autorise rien. Le renouvellement reste l'endroit où l'on refuse
d'émettre un nouvel access token pour un compte disparu, ce qui est déjà une
raison suffisante d'y relire la base.

### 3. Rotation

Chaque renouvellement **consomme** l'ancien refresh token et en émet un nouveau,
dans la même `family_id`. Un token qui resterait valable des jours après usage
serait aussi dangereux qu'un mot de passe volé.

### 4. Détection de rejeu: le mécanisme à comprendre

Si un token **déjà consommé** est présenté, deux explications:

1. un client maladroit (deux onglets qui renouvellent en même temps);
2. un token volé — l'attaquant utilise sa copie, ou la victime utilise la sienne
   après l'attaquant.

On ne peut pas les distinguer. On choisit donc la sécurité: **on révoque toute la
famille**. Le vrai utilisateur devra se reconnecter (il peut), l'attaquant aussi
(il ne peut pas).

C'est vérifié par un test: après un rejeu, plus aucun token actif dans la famille,
et la victime elle-même est déconnectée. Ce coût est assumé et il faut le dire —
c'est le genre de décision qu'on documente avant qu'un utilisateur ne se plaigne.

### 5. Révoquer vraiment

```python
# logout
if refresh:
    self.__refresh_token_service.revoke(refresh)
```

Supprimer le cookie ne suffirait pas: une copie du token continuerait de
fonctionner pendant des jours.

Et au changement de mot de passe (`PasswordResetService.reset`):

```python
self.__refresh_token_service.revoke_all_for_user(user.user_id)
```

Sinon quelqu'un qui a volé un refresh token garde l'accès, alors que la victime
croit avoir reprisle contrôle en changeant son mot de passe.

### 6. La limite qui reste, mesurée

Un test de cette étape la formule en deux assertions:

- après révocation, **l'access token en cours fonctionne encore** — on ne peut pas
  rappeler un token déjà émis;
- dès qu'il expire, la déconnexion est effective.

La fenêtre de compromission est donc au plus `JWT_ACCESS_MINUTES`. **C'est pour ça
qu'il est court.** Le seul moyen de la ramener à zéro serait de vérifier chaque
access token en base — et de perdre l'intérêt du JWT.

### 7. Plusieurs appareils

Une connexion = une **famille**. Se connecter sur son téléphone ne déconnecte pas
l'ordinateur, et déconnecter l'un ne touche pas l'autre (testé). Un rejeu, en
revanche, ne tue que la famille concernée.

Ce qui n'est **pas** fait: le ménage. `purge_expired()` existe mais rien ne
l'appelle — la table grossit. C'est un exercice.

---

## Exercices

Voir [`EXERCICES.md`](EXERCICES.md).

## Pour aller plus loin

[`docs/20-jwt-refresh-token.md`](docs/20-jwt-refresh-token.md)

---

## Fin du deuxième bloc

Les étapes 01 à 09 construisent l'application, 10 à 15 la durcissent et
remplacent son authentification. Le **troisième bloc** (16 à 21) reprend le
framework maison et ouvre l'application: rangement des abstractions, DTO
multiples, internationalisation, second facteur, API JSON, supervision.

Suite: [`../16-abstractions-du-framework/`](../16-abstractions-du-framework/).

Pour le projet d'équipe final, voir
[`../09-projet-final/docs/14-projet-equipe-helpdesk-framework-maison.md`](../09-projet-final/docs/14-projet-equipe-helpdesk-framework-maison.md).
