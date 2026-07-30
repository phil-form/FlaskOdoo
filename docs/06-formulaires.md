# 06 — Formulaires (WTForms / Flask-WTF)

Fichiers: `app/forms/`

## Un formulaire = une classe

```python
class ItemForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired(), Length(min=2, max=255)])
    description = TextAreaField('Description', validators=[DataRequired()])
    stock = IntegerField('Stock', validators=[InputRequired(), NumberRange(min=0)])
```

`FlaskForm` (Flask-WTF) ajoute deux choses à WTForms:

- il lit **automatiquement** `request.form` (pas besoin de le passer);
- il ajoute un champ CSRF caché signé avec `SECRET_KEY`.

Le premier argument (`'Nom'`) est le **label** affiché. Le nom de l'attribut
Python (`name`) est le `name=` du HTML, donc la clé dans `request.form` — il doit
correspondre à ce que le template envoie.

## Le cycle GET / POST

```python
@app.route('/items/add', methods=['GET', 'POST'])
def item_add():
    form = ItemForm()

    if form.validate_on_submit():          # POST + CSRF valide + validators OK
        item_service.insert(form)
        return redirect(url_for('item_list'))

    return render_template('items/add_or_update.html', form=form, item=None)
```

`validate_on_submit()` = `request.method in ('POST','PUT',…)` **et**
`form.validate()`. Il remplit `form.errors` en cas d'échec, et comme on
réaffiche le même formulaire, l'utilisateur retrouve ses saisies **et** les
messages d'erreur. C'est tout le confort du MVC serveur: une seule fonction, un
seul template, deux comportements.

Trois façons d'alimenter un formulaire:

```python
ItemForm()                 # lit request.form (POST), vide en GET
ItemForm(obj=item)         # pré-remplit depuis un objet (attributs de même nom)
ItemForm(data={'name': 'x'})  # pré-remplit depuis un dict
```

En POST, les données envoyées ont priorité sur `obj`: on peut donc écrire
`ItemForm(obj=item)` inconditionnellement, ce que fait `item_update`.

## Les validators

| Validator | Rôle |
|---|---|
| `DataRequired()` | valeur présente **et truthy** |
| `InputRequired()` | champ présent dans la requête, même vide/`0` |
| `Length(min=, max=)` | longueur d'une chaîne |
| `NumberRange(min=, max=)` | bornes d'un nombre |
| `Email()` | format d'email (nécessite `email-validator`) |
| `EqualTo('autre_champ')` | égalité (confirmation de mot de passe) |
| `Optional()` | champ facultatif: stoppe la validation s'il est vide |
| `Regexp(r'...')` | expression régulière |

**Le piège `DataRequired` vs `InputRequired`**: `DataRequired` teste la valeur
comme un booléen. Or `0` est falsy en Python. Un champ `stock` avec
`DataRequired()` refuse donc « 0 » — ce qui est un stock parfaitement légitime.
D'où `InputRequired()` sur les nombres, dans `ItemForm`.

Autre subtilité: sur un `IntegerField`, si la conversion échoue (« abc »), la
valeur devient `None` et WTForms ajoute lui-même l'erreur « Not a valid integer
value ».

### Des validators qui dépendent de l'environnement

Une liste de validators est une liste Python ordinaire: rien n'empêche de la
construire. `user_register_form.py` s'en sert pour être souple en développement
et strict en production:

```python
PASSWORD_VALIDATORS = (
    [DataRequired(), Length(min=4, max=128)]                    # DEBUG
    if app.debug else
    [DataRequired(), Length(min=12, max=128),                   # PRODUCTION
     Regexp(r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)',
            message="...une minuscule, une majuscule et un chiffre.")]
)

class UserRegisterForm(FlaskForm):
    password = PasswordField('Mot de passe',
                             validators=[*PASSWORD_VALIDATORS,
                                         EqualTo('confirm', message='...')])
```

Trois points:

- `*PASSWORD_VALIDATORS` **déballe** la liste choisie, et on y ajoute les
  validators propres au champ (ici `EqualTo`).
- La ternaire est évaluée **une seule fois**, à l'import du module (`app.debug`
  est déjà défini à ce moment, voir l'ordre de `app/__init__.py`). Il n'y a donc
  aucun test à chaque requête, et aucun doute sur les règles appliquées.
- La liste est **importée** par `user_reset_password_form.py`: un mot de passe
  défini via un lien de réinitialisation obéit aux mêmes règles. Dupliquer les
  validators, c'est risquer de durcir une porte en laissant l'autre ouverte.

## Validation côté serveur, toujours

Les attributs HTML `required`, `min`, `type="number"` améliorent l'expérience
mais ne protègent rien: n'importe qui peut envoyer une requête sans passer par le
formulaire (outils de développement, `curl`, script). **Toute** règle doit
exister dans les validators, et les contraintes vitales aussi dans la base
(`nullable=False`, `unique=True`).

Trois niveaux, trois rôles:

| Niveau | Exemple | Sert à |
|---|---|---|
| HTML | `required`, `min="0"` | prévenir l'utilisateur tout de suite |
| WTForms | `validators=[...]` | **décider** si la donnée est acceptée |
| Base | `nullable=False`, `unique` | garantir l'intégrité, même en cas de bug |

C'est pour ça que `UserService.insert()` entoure quand même son `commit()` d'un
`try/except`: deux inscriptions simultanées avec le même nom peuvent passer les
validators et se heurter à la contrainte unique. Le service traduit alors
l'exception en message utilisateur.

## Les champs à choix (et l'escalade de privilèges)

```python
class UserUpdateForm(FlaskForm):
    roles = SelectMultipleField('Rôles', coerce=int, validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_service = RoleService()
        self.roles.choices = [(r.role_id, r.role_name)
                              for r in self.role_service.find_all_entities()]
```

- `choices` est rempli **dynamiquement** depuis la base, dans `__init__`.
- WTForms **rejette** toute valeur absente de `choices`. Poster `roles=42` alors
  qu'aucun rôle n° 42 n'existe est donc refusé automatiquement.
- `coerce=int` convertit les valeurs (qui arrivent en texte) en entiers.

Attention: ce contrôle vérifie que la valeur est *possible*, pas que
l'utilisateur a le *droit* de l'envoyer. Rien n'empêche un simple utilisateur de
poster `roles=<id de ADMIN>`, puisque cet id existe. C'est pourquoi le controller
tranche:

```python
if current_user.is_admin():
    user_service.update_roles(user_id, form.selected_roles())
```

Le template cache le champ aux non-admins; le controller **refuse** de l'appliquer.
Les deux sont nécessaires, et seul le second est de la sécurité.

## CSRF

Une attaque CSRF, c'est un site tiers qui fait envoyer une requête à votre
application par le navigateur de la victime, en profitant de son cookie de
session:

```html
<!-- sur site-pirate.example -->
<form action="https://votre-app/users/1/delete" method="post">
<script>document.forms[0].submit()</script>
```

La parade: un jeton imprévisible, lié à la session, exigé pour chaque requête qui
modifie l'état. Le site tiers ne peut pas le connaître.

Dans le projet:

```python
csrf = CSRFProtect(app)        # app/__init__.py
```

`CSRFProtect` étend la vérification à **toutes** les requêtes POST/PUT/DELETE, y
compris celles sans formulaire WTForms (nos boutons « supprimer »). Côté
template, deux formes:

```jinja
{{ form.hidden_tag() }}                                            {# avec un FlaskForm #}
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"> {# sans #}
```

**Oublier `form.hidden_tag()` est l'erreur n°1** avec Flask-WTF: le formulaire
« ne fait rien », `validate_on_submit()` renvoie toujours `False`, et l'erreur
n'apparaît que dans `form.errors['csrf_token']`.

Pour une API consommée par un client non-navigateur (pas de cookie, donc pas de
CSRF possible), on désactive par formulaire:

```python
class MonForm(FlaskForm):
    class Meta:
        csrf = False
```

Dans les tests automatisés, on désactive globalement:
`app.config['WTF_CSRF_ENABLED'] = False`.

## Afficher un formulaire proprement

Le rendu répétitif (label + champ + erreurs) est factorisé dans une macro Jinja,
`app/templates/macros/form_macros.html`:

```jinja
{% from "macros/form_macros.html" import render_field %}

<form method="post">
    {{ form.hidden_tag() }}
    {{ render_field(form.username) }}
    {{ render_field(form.password) }}
    <button type="submit" class="btn btn-primary">Envoyer</button>
</form>
```

Voir [11-templates-jinja.md](11-templates-jinja.md) pour les macros.
