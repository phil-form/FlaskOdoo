# Projet d'équipe — Helpdesk « Delvaux & Fils »

> **Framework maison (base `pythonORM`) · Équipe de 4 · Durée : 5 jours**
> Architecture en couches façon Odoo — l'ORM est délégué à SQLAlchemy, tout le reste suit le framework du dépôt.

---

## En bref (paramètres ajustables)

| Paramètre | Valeur par défaut | À adapter                             |
|---|---|---------------------------------------|
| Taille de l'équipe | 4 apprenants | 3 = fusionner les tranches 3 et 4     |
| Durée | 5 jours | Compressible à 3 en coupant les bonus |
| Base de code | Squelette **`phil-form/pythonORM`** | —                                     |
| Stack | Flask + SQLAlchemy + Flask-Migrate, PostgreSQL, WTForms, argon2, PyJWT, injecteur maison | —                                     |
| Base de données | PostgreSQL via `docker-compose` | —                                     |
| Front | Templates Jinja + `ajax-tools.js` fournis (API JSON) | --                                    |
| Blueprints | Non utilisés (le framework auto-découvre les contrôleurs) | —                                     |

---

## 1. Contexte client

**Delvaux & Fils** est une PME belge d'environ 200 personnes (logistique). Le support informatique interne gère aujourd'hui les demandes des employés **par e-mail et via un fichier Excel partagé** : demandes perdues, aucune traçabilité, aucune statistique.

La direction vous mandate pour livrer une **application web de gestion de tickets (helpdesk)** qui remplacera le fichier Excel : un employé déclare un problème, un technicien le prend en charge, le responsable IT pilote l'ensemble (parc matériel, SLA, satisfaction).

Vous êtes 4 développeurs. Vous partez du **squelette `pythonORM`** et devez cadrer, vous répartir, développer en parallèle, intégrer, tester et présenter.

---

## 2. Objectifs pédagogiques

- Développer dans une **architecture en couches** stricte (le framework du dépôt), en préparation d'Odoo.
- Modéliser un domaine riche (**14 tables**) et ses relations 1-N, 1-1, N-M avec SQLAlchemy.
- Écrire, pour chaque entité, **toute la pile** : modèle → form → DTO → mapper → service → contrôleur → vue.
- Utiliser l'**injecteur de dépendances** et respecter le sens des dépendances.
- Gérer l'**authentification JWT**, le **hachage argon2** et les **rôles** (N-M `User`/`Role`).
- Collaborer avec **Git** et les **migrations** Flask-Migrate.

---

## 3. Périmètre fonctionnel

### 3.1 Rôles (table `roles`, N-M via `userroles`)

| Rôle (`rolename`) | Qui | Peut faire |
|---|---|---|
| `CLIENT` | Employé | Créer et suivre *ses* tickets, commenter, noter la résolution |
| `TECHNICIEN` | Membre d'une équipe support | Voir tous les tickets, s'assigner, changer le statut, documenter des solutions |
| `ADMIN` | Responsable IT | + gérer utilisateurs, équipes, parc, référentiels, statistiques |

### 3.2 Cycle de vie d'un ticket

```
   [nouveau] ──▶ [en_cours] ──▶ [resolu] ──▶ [ferme]
                     │                          ▲
                     └──────────────────────────┘  (réouverture)
```

Le client ne change pas le statut. **Chaque changement écrit une ligne** dans `ticketstatushistories` — idéalement via une méthode métier `change_status()` portée par l'entité `Ticket` (comme `add_role`/`add_item` dans le dépôt).

---

## 4. Modèle de données (14 tables) — conventions du dépôt

> Conventions `pythonORM` : table **au pluriel en minuscules** (`tickets`), colonnes **préfixées** par l'entité (`tickettitle`), PK `<entité>id`, entités qui héritent de `(BaseEntity, db.Model)`.
>
> `BaseEntity` fournit déjà à **toutes** les tables : `createdate`, `updatedate`, `deletedate`, `active`. → Le *soft delete* se fait via `active=False` et les services filtrent sur `active=True` (voir `UserService.find_all`).
>
> ⚠️ Les **modèles sont écrits ensemble le jour 1**. Ensuite chacun possède les couches supérieures de ses entités.

### 4.1 Répartition des tables

| # | Table | Propriétaire | Rôle |
|---|---|---|---|
| 1 | `users` | Dev A | Comptes |
| 2 | `roles` | Dev A | Rôles (CLIENT/TECHNICIEN/ADMIN) |
| 3 | `userroles` *(N-M)* | Dev A | Liaison user ↔ role |
| 4 | `teams` | Dev A | Équipes du support |
| 5 | `sites` | Dev A | Sites / bâtiments |
| 6 | `categories` | Dev B | Catégories de demande |
| 7 | `priorities` | Dev B | Référentiel priorité + SLA |
| 8 | `tickets` | Dev B | Cœur du système |
| 9 | `comments` | Dev C | Fil de discussion |
| 10 | `ticketstatushistories` | Dev C | Journal des statuts |
| 11 | `attachments` | Dev C | Pièces jointes |
| 12 | `equipments` | Dev D | Parc matériel |
| 13 | `knowledgearticles` | Dev D | Base de connaissances |
| 14 | `satisfactionsurveys` | Dev D | Enquête (1 par ticket) |

*Tables non-liaison par personne : A=4, B=3, C=3, D=3 → contrainte « ≥ 2 hors N-M » respectée. La liaison `userroles` réutilise le patron `UserRole` du dépôt.*

### 4.2 Colonnes (hors champs hérités de `BaseEntity`)

**`users`** — userid *(PK)* · username *(unique)* · useremail *(unique)* · userpassword *(argon2)* · userfirstname · userlastname · teamid → `teams` *(null)* · siteid → `sites` *(null)*
 · relations : `roles` (`UserRole`), tickets créés / assignés.
 · méthodes métier : `add_role`, `get_roles`, `is_admin`, `has_role("TECHNICIEN")`.

**`roles`** — roleid *(PK)* · rolename *(unique)* · relation `users` (`UserRole`).

**`userroles`** *(association N-M)* — roleid *(FK, PK)* · userid *(FK, PK)* · `rel_user` · `rel_role`.

**`teams`** — teamid *(PK)* · teamname *(unique)* · teamdescription · relation `members`.

**`sites`** — siteid *(PK)* · sitename · siteaddress · sitecity · relations `users`, `equipments`.

**`categories`** — categoryid *(PK)* · categoryname *(unique)* · categorydescription.

**`priorities`** — priorityid *(PK)* · priorityname *(unique)* · prioritylevel *(int)* · prioritydelayhours *(int, SLA)*.

**`tickets`** — ticketid *(PK)* · tickettitle · ticketdescription · ticketstatus · ticketduedate *(null, dérivée du SLA)* · authorid → `users` · technicianid → `users` *(null)* · categoryid → `categories` · priorityid → `priorities` · equipmentid → `equipments` *(null)*
 · relations : `comments`, `histories`, `attachments`, `survey` (1-1).

**`comments`** — commentid *(PK)* · commentcontent · authorid → `users` · ticketid → `tickets`.

**`ticketstatushistories`** — historyid *(PK)* · ticketid → `tickets` · userid → `users` · oldstatus · newstatus *(l'horodatage vient de `createdate`)*.

**`attachments`** — attachmentid *(PK)* · attachmentfilename · attachmentpath · attachmentsize · ticketid → `tickets` · authorid → `users`.

**`equipments`** — equipmentid *(PK)* · equipmentname · equipmenttype · equipmentserial *(unique)* · equipmentpurchasedate · siteid → `sites` · userid → `users` *(null)*.

**`knowledgearticles`** — articleid *(PK)* · articletitle · articlecontent · categoryid → `categories` · authorid → `users`.

**`satisfactionsurveys`** — surveyid *(PK)* · surveyrating *(1-5)* · surveycomment · ticketid → `tickets` *(**unique** → 1-1)* · clientid → `users`.

---

## 5. Architecture imposée (framework `pythonORM`)

### 5.1 Les couches et le sens des dépendances

```
   models  ◀── forms      (le modèle ne dépend de rien)
     ▲  ▲       ▲
     │  └── dtos│
     │      ▲   │
   mappers ─┘   │   (mappers → models, dtos, forms)
     ▲          │
   services ────┘   (services → models, mappers)
     ▲
   controllers      (controllers → services)
     ▲
   templates + static/js  (la « vue »)
```

Règle d'or (README du dépôt, §6), à ne jamais inverser :
- **mappers** dépendent des modèles, des DTOs et des forms ;
- **services** dépendent des modèles et des mappers ;
- **controllers** dépendent des services.

### 5.2 Rôle de chaque couche

| Couche | Dossier | Convention imposée |
|---|---|---|
| **Modèle** | `app/models/` | `(BaseEntity, db.Model)`, colonnes préfixées, méthodes métier sur l'entité |
| **Form** | `app/forms/<domaine>/` | `FlaskForm`, `.from_json(request.json)` |
| **DTO** | `app/dtos/` | hérite `AbstractDTO` : `build_from_entity(entity)` + `get_json_parsable()` |
| **Mapper** | `app/mappers/` | hérite `AbstractMapper` : `entity_to_dto(entity)`, `form_to_entity(form, entity)` |
| **Service** | `app/services/` | hérite `BaseService` : `find_all / find_one / find_one_by / insert / update / delete` |
| **Contrôleur** | `app/controllers/` | `@app.route('/...')` + `@auth_required(level=...)` + `@inject` |
| **Vue** | `app/templates/`, `app/static/js/` | Jinja |

### 5.3 Injection de dépendances

Chaque service doit être **enregistré dans `app/framework/config/injector_config.py`** avec un scope (`SINGLETON`, `SCOPED` ou `TRANSIENT`). Un contrôleur reçoit son service par **annotation de type** grâce à `@inject` :

```python
@app.route('/api/tickets')
@auth_required()
@inject
def getTicketList(ticket_service: TicketService):
    return jsonify([t.get_json_parsable() for t in ticket_service.find_all()])
```

> ⚠️ **`injector_config.py` est le seul fichier vraiment partagé.** Contrôleurs et modèles sont **auto-découverts** par glob (`app/controllers/__init__.py` + `from app.controllers import *`), donc **ajouter un contrôleur ou un modèle ne demande de toucher à aucun fichier commun**. Seul l'enregistrement des services impose une édition concertée (en mode *append*, pour limiter les conflits Git).

### 5.4 Sécurité

- Mots de passe **hachés avec argon2** (`argon2.PasswordHasher().hash(..)` / `argon2.PasswordHasher().verify(...)`, comme `UserService`).
- Authentification par **JWT** (`login` renvoie un token) et protection des routes via `@auth_required(level="ADMIN", or_is_current_user=True)`.
- Contrôle de rôle sur **chaque route sensible** ; un CLIENT ne voit que ses tickets.

---

## 6. Mise en route (jour 1, ensemble)

1. Cloner/forker le squelette `pythonORM`, créer le dépôt d'équipe, `.gitignore`.
2. `docker-compose up -d` pour PostgreSQL, remplir `.env.local` (`DATABASE_URL`, `JWT_KEY`, `CORS_ORIGIN`).
3. Nettoyer le domaine d'exemple (panier/items) pour repartir du helpdesk.
4. **Écrire ensemble les 14 modèles** + relations + méthodes métier clés (`Ticket.change_status`, `User.add_role`).
5. Initialiser et appliquer les migrations : `./sqlAlchemy.sh -i` puis `-m init_helpdesk` puis `-u`.
6. Auth minimale (login/register JWT) fonctionnelle pour débloquer l'équipe.
7. Jeu de données de démo (via une migration de données, comme dans le dépôt) : rôles, 1 admin, 1 technicien, 1 client, sites, équipes, catégories, priorités.

Tant que ça ne tourne pas, personne ne part sur sa tranche.

---

## 7. Découpage en 4 tranches verticales

Chaque développeur écrit **toute la pile** de ses entités (form + DTO + mapper + service + contrôleur + templates) et **enregistre ses services** dans l'injecteur.

### 🔵 Tranche 1 — Comptes, rôles & organisation — *Dev A · `users`, `roles`, `userroles`, `teams`, `sites`*
- Register / login JWT, argon2, profil.
- Attribution des rôles (réutiliser `add_role`/`remove_role`), CRUD équipes et sites.
- Espace admin : liste des utilisateurs, activation/désactivation (`active`).
- Livrer tôt : le service d'auth et le décorateur de rôle, utilisés par toute l'équipe.

### 🟢 Tranche 2 — Tickets & référentiels — *Dev B · `categories`, `priorities`, `tickets`*
- CRUD catégories et priorités (avec `prioritydelayhours`).
- Création de ticket, calcul de `ticketduedate` d'après le SLA.
- « Mes tickets » vs « Tous les tickets », page détail, assignation.
- `Ticket.change_status()` qui applique le cycle §3.2 **et** délègue l'écriture du journal.

### 🟠 Tranche 3 — Échanges, journal & pièces jointes — *Dev C · `comments`, `ticketstatushistories`, `attachments`*
- Commentaires (fil chronologique).
- Journal : consommer `change_status()` pour créer/afficher l'historique.
- Upload/téléchargement sécurisés des pièces jointes.
- Filtres (statut/priorité/catégorie), recherche, pagination.

### 🟣 Tranche 4 — Parc, connaissances & pilotage — *Dev D · `equipments`, `knowledgearticles`, `satisfactionsurveys`*
- CRUD parc matériel (rattaché à site / utilisateur).
- Base de connaissances liée aux catégories.
- Enquête de satisfaction à la fermeture d'un ticket (1-1).
- Tableau de bord : tickets par statut/catégorie/technicien, SLA respectés, note moyenne, un graphique.

> **Contrats à négocier tôt (au stand-up) :** service d'auth (A → tous) · signature de `TicketService` et de `Ticket.change_status` (B ↔ C) · déclenchement de l'enquête à la fermeture (B → D) · accès aux données pour les stats (B/C/D → D).

---

## 8. Collaboration

- Branche `main` **toujours fonctionnelle** ; une branche par fonctionnalité ; merge via MR relue.
- Un **stand-up quotidien** (fait / en cours / bloqué) + un **référent intégration** tournant.
- **Migrations** : ne jamais éditer une migration déjà appliquée par un coéquipier ; en créer une nouvelle (`./sqlAlchemy.sh -m ...`).
- Point de vigilance : `injector_config.py` (édition concertée) et les migrations sont les zones à conflits — synchronisez-vous dessus.

---

## 9. Planning

| Jour | Objectif | Fin de journée |
|---|---|---|
| **J1** | Mise en route + **14 modèles** + migrations + auth minimale | Base qui tourne, seed, branches créées |
| **J2** | Piles verticales (1) | Chaque tranche a ses services + contrôleurs principaux |
| **J3** | Piles (2) + 1ʳᵉ intégration | Merges, journal & enquête branchés sur le cycle de vie, tests croisés |
| **J4** | Finitions, erreurs 403/404/500, seed réaliste, tests | App stable, README |
| **J5** | Répétition + démo + rétro | Chacun présente sa tranche |

> J3 : chacun teste la tranche d'un autre.

---

## 10. Livrables

- Dépôt Git à l'historique **propre et réparti**.
- `README.md` : installation (docker-compose, `.env`, `./sqlAlchemy.sh -i/-u`, `python3 runserver.py`), comptes de démo.
- Migration de **données de démonstration**.
- Application fonctionnelle.
- Démo orale (~15 min) où **chaque membre présente sa tranche**.

---

## 11. Grille d'évaluation (100 pts)

| Critère | Pts | Détail |
|---|---|---|
| Architecture en couches | 20 | Sens des dépendances respecté, services injectés/enregistrés, aucune requête en contrôleur ni logique en template |
| Modèle & migrations | 15 | 14 tables, relations correctes, migrations propres et rejouables |
| Fonctionnalités | 25 | Les 4 tranches couvrent le périmètre |
| Sécurité | 15 | argon2, JWT, contrôle de rôle sur chaque route sensible |
| Qualité du code | 15 | DTO/mapper corrects, conventions du dépôt, gestion des erreurs |
| Collaboration Git | 5 | Branches, MR, contributions équilibrées |
| Présentation & README | 5 | Démo claire, doc suffisante |

**Malus :** mot de passe en clair (−10), dépendance inversée / requête SQL dans un contrôleur (−10), `main` cassée à la démo (−5), changement de statut non journalisé (−5).

---

## 12. Unit Tests

- Table `Tag` + relation **N-M** avec les tickets (patron `UserRole`).
- Tests **pytest** (fixtures, base de test).
- Alertes tickets **hors délai SLA** (`ticketduedate` dépassée).
- Rafraîchissement d'un tableau via le `table-component.js` fourni (API JSON).
- Notifications e-mail à l'assignation (mode console).

---

## Annexe — Pont framework maison → Odoo

| Ce projet (`pythonORM`) | Équivalent Odoo |
|---|---|
| Entité `(BaseEntity, db.Model)` | `models.Model` |
| `createdate` / `updatedate` / `active` (`BaseEntity`) | champs automatiques `create_date` / `write_date` / `active` (archivage) |
| FK / relation N-1 | `fields.Many2one` |
| Relation 1-N | `fields.One2many` |
| Table de liaison (`UserRole`, tags) | `fields.Many2many` |
| Méthode métier sur l'entité (`change_status`, `add_role`) | méthode Python sur le modèle |
| Service `find_all/insert/update/delete` | `search` / `create` / `write` / `unlink` |
| Injecteur + `@inject` | `self.env` / registre Odoo |
| `@auth_required(level=...)` + rôles | `res.groups` + `ir.rule` |
| Migrations Flask-Migrate | mise à jour de module + fichiers `data/` |
| Template Jinja | vue **QWeb** (XML) |

> Il n'y a **pas de Blueprint** ici, comme en Odoo. Le découpage `models / services / controllers / vues` que vous pratiquez est exactement celui d'un module Odoo — c'est le but.
