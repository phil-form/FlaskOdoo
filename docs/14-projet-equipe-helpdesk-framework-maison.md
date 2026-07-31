# Projet d'équipe — Helpdesk « Delvaux & Fils »

> **Framework maison (base `pythonORM`) · Équipe de 4 (5ᵉ personne optionnelle) · Durée : 5 jours**
> Architecture en couches façon Odoo — l'ORM est délégué à SQLAlchemy, tout le reste suit le framework du dépôt.

---

## En bref (paramètres ajustables)

| Paramètre | Valeur par défaut | À adapter                             |
|---|---|---------------------------------------|
| Taille de l'équipe | 4 apprenants | **5 = ajouter la tranche 5 et ses 4 tables optionnelles** · 3 = voir §7.5 |
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

Vous êtes **4 développeurs**. Si une **5ᵉ personne** rejoint l'équipe, elle prend une **tranche supplémentaire avec ses propres tables** (suivi des interventions et étiquettes, §4.3) : le travail des quatre autres reste inchangé. Vous partez du **squelette `pythonORM`** et devez cadrer, vous répartir, développer en parallèle, intégrer, tester et présenter.

---

## 2. Objectifs pédagogiques

- Développer dans une **architecture en couches** stricte (le framework du dépôt), en préparation d'Odoo.
- Modéliser un domaine riche (**14 tables**, + 4 optionnelles à 5) et ses relations 1-N, 1-1, N-M avec SQLAlchemy.
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

## 4. Modèle de données (14 tables + 4 optionnelles) — conventions du dépôt

> Conventions `pythonORM` : table **au pluriel en minuscules** (`tickets`), colonnes **préfixées** par l'entité (`tickettitle`), PK `<entité>id`, entités qui héritent de `(BaseEntity, db.Model)`.
>
> `BaseEntity` fournit déjà à **toutes** les tables : `createdate`, `updatedate`, `deletedate`, `active`. → Le *soft delete* se fait via `active=False` et les services filtrent sur `active=True` (voir `UserService.find_all`).
>
> ⚠️ Les **14 modèles de base sont écrits ensemble le jour 1**. Ensuite chacun possède les couches supérieures de ses entités. Les **4 tables optionnelles** (§4.3) n'existent que si l'équipe compte une 5ᵉ personne : elles sont écrites par Dev E, dans **sa propre migration**.

### 4.1 Répartition des 14 tables de base

Cette répartition est **la même à 4 et à 5** : l'arrivée d'une 5ᵉ personne ne redistribue rien.

| # | Table | Propriétaire | Rôle |
|---|---|---|---|
| 1 | `users` | Dev A | Comptes |
| 2 | `roles` | Dev A | Rôles (CLIENT/TECHNICIEN/ADMIN) |
| 3 | `userroles` *(N-M)* | Dev A | Liaison user ↔ role |
| 4 | `teams` | Dev A | Équipes du support |
| 5 | `categories` | Dev B | Catégories de demande |
| 6 | `priorities` | Dev B | Référentiel priorité + SLA |
| 7 | `tickets` | Dev B | Cœur du système |
| 8 | `comments` | Dev C | Fil de discussion |
| 9 | `ticketstatushistories` | Dev C | Journal des statuts |
| 10 | `attachments` | Dev C | Pièces jointes |
| 11 | `sites` | Dev D | Sites / bâtiments |
| 12 | `equipments` | Dev D | Parc matériel |
| 13 | `knowledgearticles` | Dev D | Base de connaissances |
| 14 | `satisfactionsurveys` | Dev D | Enquête (1 par ticket) |

*Tables non-liaison par personne : A=3, B=3, C=3, D=4 → contrainte « ≥ 2 hors N-M » respectée. D porte 4 tables mais dont trois légères ; A et B portent en compensation une **brique transverse** (tableau de bord, recherche/pagination) — l'équilibrage chiffré est en §7.1. La liaison `userroles` réutilise le patron `UserRole` du dépôt.*

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

### 4.3 Tables optionnelles — *uniquement si vous êtes 5* (Dev E)

Ces 4 tables **n'existent pas** dans un projet à 4 : elles ne sont ni écrites, ni migrées, ni évaluées. Elles forment le périmètre propre de la tranche 5.

| # | Table | Rôle |
|---|---|---|
| 15 | `interventions` | Intervention d'un technicien sur un ticket (date, durée, compte rendu) |
| 16 | `interventiontypes` | Référentiel : déplacement sur site, télémaintenance, atelier… |
| 17 | `tags` | Étiquettes libres posées sur les tickets |
| 18 | `tickettags` *(N-M)* | Liaison ticket ↔ tag |

**`interventions`** — interventionid *(PK)* · interventiondate · interventionduration *(int, minutes)* · interventionreport *(compte rendu)* · ticketid → `tickets` · technicianid → `users` · interventiontypeid → `interventiontypes`.

**`interventiontypes`** — interventiontypeid *(PK)* · interventiontypename *(unique)* · interventiontypedescription.

**`tags`** — tagid *(PK)* · tagname *(unique)* · tagcolor.

**`tickettags`** *(association N-M)* — tagid *(FK, PK)* · ticketid *(FK, PK)* · `rel_tag` · `rel_ticket` — même patron que `UserRole`.

> 🔒 **Règle d'isolation** : toutes les clés étrangères vont **des tables optionnelles vers les tables de base**, jamais l'inverse. Aucune tranche 1-4 ne dépend d'une table optionnelle, et le schéma d'une équipe de 4 reste **strictement identique** à celui décrit en §4.1-4.2.
>
> Seule exception à négocier avec Dev B : la relation `tags` déclarée côté `Ticket` (une ligne dans le modèle `Ticket`, comme `roles` dans `User`). Les vues de la tranche 5 (onglet « Interventions » et filtre par tag sur la page ticket) sont écrites par Dev E dans **ses propres templates/partiels**.

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
4. **Écrire ensemble les 14 modèles de base** + relations + méthodes métier clés (`Ticket.change_status`, `User.add_role`). Les tables optionnelles (§4.3) ne sont **pas** de la partie : Dev E les ajoutera dans sa propre migration.
5. Initialiser et appliquer les migrations : `./sqlAlchemy.sh -i` puis `-m init_helpdesk` puis `-u`.
6. Auth minimale (login/register JWT) fonctionnelle pour débloquer l'équipe.
7. Jeu de données de démo (via une migration de données, comme dans le dépôt) : rôles, 1 admin, 1 technicien, 1 client, sites, équipes, catégories, priorités.
8. Fixer l'effectif : à 4, on s'arrête aux tranches 1-4 ; à 5, Dev E prend la **tranche 5 optionnelle** (§4.3 + §7.3).

Tant que ça ne tourne pas, personne ne part sur sa tranche.

---

## 7. Découpage en tranches verticales

Chaque développeur écrit **toute la pile** de ses entités (form + DTO + mapper + service + contrôleur + templates) et **enregistre ses services** dans l'injecteur.

Le périmètre de base tient en **4 tranches de poids égal**. Une équipe de 5 ajoute la **tranche 5**, qui repose sur **ses propres tables optionnelles** (§4.3) : elle **n'enlève rien** aux quatre autres et n'est pas un prérequis pour elles.

### 7.1 Équilibre des tranches

Une tranche « pèse » la somme de ses entités et de sa brique transverse, avec le barème suivant :

| Poids | Éléments |
|---|---|
| **3** | `tickets` (cœur du système) |
| **2** | `users`, `comments`, `ticketstatushistories`, `attachments`, `equipments`, `knowledgearticles`, `interventions`, brique **tableau de bord** |
| **1** | `roles`, `teams`, `sites`, `categories`, `priorities`, `satisfactionsurveys`, `interventiontypes`, `tags`, `tickettags`, briques **recherche / filtres / pagination** et **rapport de temps** |
| **0** | `userroles` (copie du patron `UserRole` du dépôt) et l'auth minimale, écrite **ensemble le jour 1** (§6) |

**Les 4 tranches de base — 6 points chacune, à 4 comme à 5 :**

| Tranche | Entités | Brique transverse | Poids |
|---|---|---|---|
| 1 · Dev A | `users`, `roles`, `userroles`, `teams` | tableau de bord | 2+1+0+1 +2 = **6** |
| 2 · Dev B | `categories`, `priorities`, `tickets` | recherche / filtres / pagination | 1+1+3 +1 = **6** |
| 3 · Dev C | `comments`, `ticketstatushistories`, `attachments` | — | 2+2+2 = **6** |
| 4 · Dev D | `sites`, `equipments`, `knowledgearticles`, `satisfactionsurveys` | — | 1+2+2+1 = **6** |

**Tranche 5 — activée seulement à 5, calibrée sur le même poids :**

| Tranche | Entités *(optionnelles, §4.3)* | Brique transverse | Poids |
|---|---|---|---|
| 5 · Dev E | `interventions`, `interventiontypes`, `tags`, `tickettags` | rapport de temps par technicien | 2+1+1+1 +1 = **6** |

### 7.2 Les quatre tranches de base

#### 🔵 Tranche 1 — Comptes, rôles & pilotage — *Dev A · `users`, `roles`, `userroles`, `teams`*
- Finaliser register / login JWT amorcés le jour 1, argon2, profil, changement de mot de passe.
- Attribution des rôles (réutiliser `add_role`/`remove_role`), CRUD équipes, affectation des membres.
- Espace admin : liste des utilisateurs, activation/désactivation (`active`).
- **Tableau de bord** : tickets par statut / catégorie / technicien, SLA respectés, note moyenne, au moins un graphique.
- Livrer tôt : le service d'auth et le décorateur de rôle, utilisés par toute l'équipe. Le tableau de bord, lui, ne se branche qu'à partir de J3, quand les autres tranches produisent des données.

#### 🟢 Tranche 2 — Tickets & référentiels — *Dev B · `categories`, `priorities`, `tickets`*
- CRUD catégories et priorités (avec `prioritydelayhours`).
- Création de ticket, calcul de `ticketduedate` d'après le SLA.
- « Mes tickets » vs « Tous les tickets », page détail, assignation.
- `Ticket.change_status()` qui applique le cycle §3.2 **et** délègue l'écriture du journal.
- **Brique transverse** : filtres (statut / priorité / catégorie), recherche et pagination, écrits pour être **réutilisés par toutes les listes de l'application** (parc, articles, interventions).

#### 🟠 Tranche 3 — Échanges, journal & pièces jointes — *Dev C · `comments`, `ticketstatushistories`, `attachments`*
- Commentaires (fil chronologique).
- Journal : consommer `change_status()` pour créer/afficher l'historique.
- Upload / téléchargement **sécurisés** des pièces jointes : validation du type et de la taille, chemin de stockage non devinable, contrôle d'accès au téléchargement.

#### 🟣 Tranche 4 — Sites, parc & connaissances — *Dev D · `sites`, `equipments`, `knowledgearticles`, `satisfactionsurveys`*
- CRUD sites / bâtiments.
- CRUD parc matériel (rattaché à un site et, éventuellement, à un utilisateur), rattachement d'un équipement à un ticket.
- Base de connaissances liée aux catégories.
- Enquête de satisfaction à la fermeture d'un ticket (relation 1-1, une seule réponse par ticket).

### 7.3 🔴 Tranche 5 — optionnelle, uniquement à 5 — *Dev E · `interventions`, `interventiontypes`, `tags`, `tickettags`*

Périmètre **entièrement additif** : un groupe de 4 ne l'écrit pas et son application reste complète.

- CRUD du référentiel des types d'intervention (déplacement sur site, télémaintenance, atelier…).
- Saisie d'une **intervention** sur un ticket : date, durée, compte rendu, technicien — visible depuis la page détail du ticket (onglet dédié).
- **Étiquettes** (`tags`) posées sur les tickets via la liaison N-M `tickettags` (patron `UserRole`), plus filtre par étiquette branché sur la brique de recherche de Dev B.
- **Brique transverse** : rapport de temps — total des durées par technicien, par équipe et par période.
- Écrit sa propre migration (`./sqlAlchemy.sh -m add_interventions`), **après** `init_helpdesk`, et étend le seed avec quelques types d'intervention et étiquettes.

### 7.4 Contrats à négocier tôt (au stand-up)

- Service d'auth et décorateur de rôle : **A → tous**.
- Signature de `TicketService` et de `Ticket.change_status` : **B ↔ C**.
- Brique recherche / filtres / pagination : **B → tous** (interface figée avant J3).
- Déclenchement de l'enquête à la fermeture : **B → D**.
- Accès aux données pour les statistiques : **B/C/D → A**.
- *À 5 uniquement* : la relation `tags` déclarée dans le modèle `Ticket` et le point d'accroche de l'onglet « Interventions » dans la page détail : **E → B**.

### 7.5 Adapter à l'effectif réel

| Effectif | Règle |
|---|---|
| **4** | Tranches 1 à 4, 6 points chacune. Les tables optionnelles du §4.3 ne sont pas écrites — rien d'autre ne change. |
| **5** | Idem + tranche 5 et ses 4 tables optionnelles, calibrée sur le même poids (6). Aucune redistribution entre A, B, C et D. |
| **3** | Tranches 1 à 3 conservées ; la tranche 4 est démontée : `sites` et `equipments` → **A**, `knowledgearticles` et `satisfactionsurveys` → **C**. ~8 points chacun : prévoyez de couper des bonus. |

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
| **J1** | Mise en route + **14 modèles de base** + migrations + auth minimale | Base qui tourne, seed, branches créées |
| **J2** | Piles verticales (1) *(à 5 : E écrit ses modèles optionnels + sa migration)* | Chaque tranche a ses services + contrôleurs principaux |
| **J3** | Piles (2) + 1ʳᵉ intégration | Merges, journal & enquête branchés sur le cycle de vie, tests croisés |
| **J4** | Finitions, erreurs 403/404/500, seed réaliste, tests | App stable, README |
| **J5** | Répétition + démo + rétro | Chacun présente sa tranche |

> J3 : chacun teste la tranche d'un autre (rotation circulaire : A→B→C→D→(E)→A).
>
> Deux briques dépendent des données produites par les autres et ne se branchent qu'à partir de J3 : le **tableau de bord** (A) et le **rapport de temps** (E). J2 sert à en écrire les entités et le CRUD.

---

## 10. Livrables

- Dépôt Git à l'historique **propre et réparti**.
- `README.md` : installation (docker-compose, `.env`, `./sqlAlchemy.sh -i/-u`, `python3 runserver.py`), comptes de démo.
- Migration de **données de démonstration**.
- Application fonctionnelle.
- Démo orale (~15 min à 4, ~20 min à 5 — **3 à 4 min par personne**) où **chaque membre présente sa tranche**.

---

## 11. Grille d'évaluation (100 pts)

| Critère | Pts | Détail |
|---|---|---|
| Architecture en couches | 20 | Sens des dépendances respecté, services injectés/enregistrés, aucune requête en contrôleur ni logique en template |
| Modèle & migrations | 15 | Les **14 tables de base**, relations correctes, migrations propres et rejouables |
| Fonctionnalités | 25 | Les 4 tranches de base couvrent le périmètre |
| Sécurité | 15 | argon2, JWT, contrôle de rôle sur chaque route sensible |
| Qualité du code | 15 | DTO/mapper corrects, conventions du dépôt, gestion des erreurs |
| Collaboration Git | 5 | Branches, MR, contributions équilibrées |
| Présentation & README | 5 | Démo claire, doc suffisante |

**Malus :** mot de passe en clair (−10), dépendance inversée / requête SQL dans un contrôleur (−10), `main` cassée à la démo (−5), changement de statut non journalisé (−5).

> **La grille est identique à 4 et à 5.** Une équipe de 4 n'est pas pénalisée pour l'absence des tables optionnelles. À 5, la tranche 5 est évaluée **sur les mêmes critères** que les autres (architecture, sécurité, qualité) : elle apporte du périmètre, pas des points bonus.

---

## 12. Tests unitaires & bonus

Les tests **pytest** (fixtures, base de test) concernent **tout le monde** : chacun teste les services de sa propre tranche — même volume attendu par personne.

Les bonus sont eux aussi répartis **un par tranche**, pour que le supplément de travail reste équilibré :

| Bonus | Tranche |
|---|---|
| Export CSV des statistiques + second graphique | 1 · Dev A |
| Alertes tickets **hors délai SLA** (`ticketduedate` dépassée) | 2 · Dev B |
| Notifications e-mail à l'assignation (mode console) | 3 · Dev C |
| Rafraîchissement d'un tableau via le `table-component.js` fourni (API JSON) | 4 · Dev D |
| Vue calendrier des interventions | 5 · Dev E *(si activée)* |

> Le bonus de la tranche 5 tombe avec elle : à 4, personne ne le reprend.
>
> Les **étiquettes** (`tags` + N-M `tickettags`) appartiennent à la tranche 5. Une équipe de 4 qui veut quand même exercer la relation N-M au-delà de `userroles` peut les prendre en bonus d'équipe — hors périmètre évalué.

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
