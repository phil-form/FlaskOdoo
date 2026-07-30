# 05 — DTOs & mappers

Fichiers: `app/dtos/`, `app/mappers/`

## Le problème: donner une entité à un template

Tentant, mais trois ennuis:

1. **La session SQLAlchemy.** Une entité est un objet « vivant »: accéder à
   `user.roles` déclenche une requête SQL si la relation n'est pas encore
   chargée. Depuis un template, cela veut dire des requêtes cachées au milieu du
   rendu — et une `DetachedInstanceError` si la session est déjà fermée.
2. **Les données sensibles.** `User` contient `password` (le hash). Un
   `{{ user.password }}` par erreur, ou un `jsonify(user.__dict__)`, et il part
   dans la page.
3. **Le couplage.** Renommer une colonne casserait tous les templates qui
   l'utilisent.

## La solution: un objet de transport figé

```python
class UserDTO(AbstractDTO):
    def __init__(self):
        self.user_id = None
        self.username = None
        self.email = None
        self.description = None
        self.roles = []            # des RoleDTO, pas des UserRole

    @staticmethod
    def build_from_entity(user):
        user_dto = UserDTO()
        user_dto.user_id = user.user_id
        ...
        user_dto.roles = [RoleDTO.build_from_entity(ur.role) for ur in user.roles]
        return user_dto
```

Pas de `password`: il n'existe simplement pas dans le DTO. Et les relations sont
**déjà résolues** au moment où le template les lit: plus aucune requête pendant
le rendu.

Un DTO peut porter des méthodes de confort, du moment qu'elles ne touchent pas la
base:

```python
def role_names(self):  return [role.role_name for role in self.roles]
def is_admin(self):    return "ADMIN" in self.role_names()
```

C'est ce qui permet au layout d'écrire `{% if current_user.is_admin() %}`.

## Le contrat AbstractDTO

```python
class AbstractDTO(ABC):
    @staticmethod
    @abstractmethod
    def build_from_entity(entity): ...

    @abstractmethod
    def get_json_parsable(self): ...
```

`get_json_parsable()` renvoie un dictionnaire de types de base, prêt pour
`jsonify()`. Inutile dans un projet 100% MVC — mais c'est exactement le point de
bascule si vous ajoutez une API à côté des pages: les DTO sont déjà prêts.

Piège corrigé dans ce projet: la version d'origine faisait

```python
def get_json_parsable(self):
    self.roles = [r.get_json_parsable() for r in self.roles]   # ← modifie self!
    return self.__dict__
```

Après un appel, `self.roles` contient des dictionnaires et `role_names()`
plante. La bonne version construit une copie:

```python
def get_json_parsable(self):
    data = dict(self.__dict__)
    data['roles'] = [role.get_json_parsable() for role in self.roles]
    return data
```

Règle générale: une méthode nommée `get_...` ne doit pas modifier l'objet.

## Un DTO, deux entités sources

`ItemDTO` sait se construire depuis un `Item` (catalogue) **ou** depuis un
`BasketItem` (panier):

```python
@staticmethod
def build_from_entity(entity):
    item_dto = ItemDTO()
    if isinstance(entity, Item):
        item_dto.quantity = entity.stock          # quantité disponible
        ...
    elif isinstance(entity, BasketItem):
        item_dto.quantity = entity.quantity       # quantité commandée
        item_dto.name = entity.item.name
        ...
    return item_dto
```

Grâce à ça, le fragment `templates/items/_item_table.html` sert **à la fois** au
catalogue et au panier: même tableau, deux sources de données. C'est un exemple
concret de ce que le découplage permet.

## Les mappers

Le DTO sait se construire depuis une entité; le mapper, lui, est le point
d'entrée unique des conversions, dans les deux sens:

```
 Form   --form_to_entity-->   Entity   --entity_to_dto-->   DTO
```

```python
class UserMapper(AbstractMapper):
    @staticmethod
    def entity_to_dto(entity: User) -> UserDTO:
        return UserDTO.build_from_entity(entity)

    @staticmethod
    def form_to_entity(form, user: User) -> User:
        if isinstance(form, UserRegisterForm):
            user.username = form.username.data
            user.email = form.email.data
            user.password = form.password.data       # en clair: le service hashe
            user.description = form.description.data or ""
        elif isinstance(form, UserUpdateForm):
            user.email = form.email.data             # ni username ni password!
            user.description = form.description.data or ""
        elif isinstance(form, UserLoginForm):
            ...
        return user
```

Deux choses importantes ici.

**1. Le `isinstance` est une fonctionnalité, pas une maladresse.** Chaque branche
ne recopie que les champs de *son* formulaire. C'est ce qui garantit qu'un POST
sur `/users/3/edit` ne peut pas changer le mot de passe ou le nom d'utilisateur,
même si le navigateur envoie ces champs. Le contraire — une boucle générique
`for k, v in form.data.items(): setattr(user, k, v)` — s'appelle une faille
d'*assignation de masse* (mass assignment).

**2. Les opérations privilégiées ne passent pas par le mapper.** Les rôles ne
sont pas appliqués dans `form_to_entity`: ils le sont par
`UserService.update_roles()`, appelée seulement si l'utilisateur connecté est
ADMIN. Un mapper traduit, il ne décide pas des droits.

## Faut-il toujours des DTO et des mappers ?

Sur un CRUD simple, cette couche paraît bavarde: trois fichiers pour afficher un
nom. Elle prend son sens quand:

- plusieurs vues affichent la même entité différemment,
- l'entité contient des champs à ne jamais exposer,
- une API et des pages HTML coexistent,
- les templates sont écrits par quelqu'un qui n'a pas à connaître le schéma.

Sachez pourquoi vous la mettez en place; un projet de dix routes peut
légitimement s'en passer. L'objectif de la formation est que vous puissiez
justifier le choix, pas que vous l'appliquiez mécaniquement.
