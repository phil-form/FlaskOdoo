# 11 — Templates Jinja2

Fichiers: `app/templates/`

## Les trois syntaxes

```jinja
{{ expression }}      affiche une valeur
{% instruction %}     if, for, extends, block, include, with, macro...
{# commentaire #}     n'est jamais envoyé au navigateur
```

La dernière est importante: un `<!-- commentaire HTML -->` part chez le client et
se lit dans « afficher la source ». Un commentaire Jinja n'existe qu'à la
compilation du template. Les explications techniques vont donc dans `{# ... #}`.

## Organisation du dossier

```
templates/
├── layout/main_layout.html      le squelette de toutes les pages
├── macros/form_macros.html      des "fonctions" de template
├── home/home.html  home/jinja.html
├── users/  login, register, list, profile, update
├── items/  list, details, add_or_update, _item_table.html
├── baskets/  details, list
└── seed/seed.html
```

Un fichier commençant par `_` (`_item_table.html`) est un **fragment**: il n'étend
pas le layout et n'est jamais rendu seul, il est inclus par d'autres pages.

## Héritage

Le layout définit des trous, les pages les remplissent.

```jinja
{# layout/main_layout.html #}
<title>{% block title %}Flask MVC{% endblock %}</title>   {# avec valeur par défaut #}
...
<div class="root container">
    {% block body %}{% endblock %}
</div>
```

```jinja
{# items/list.html #}
{% extends "layout/main_layout.html" %}
{% block title %}Boutique{% endblock %}
{% block body %}
    <h1>Catalogue</h1>
{% endblock %}
```

`{% extends %}` doit être la **première** instruction du fichier. Tout ce qui est
écrit hors d'un `{% block %}` dans un template enfant est ignoré.

## include vs macro

Deux façons de réutiliser du HTML, à ne pas confondre.

**`{% include %}`** insère un fichier, qui **partage le contexte** de la page:

```jinja
{% with is_basket = false %}
    {% include "items/_item_table.html" %}
{% endwith %}
```

Le fragment voit `items`, `add_form`, `current_user`, et le `is_basket` défini
juste avant par `{% with %}`. C'est ainsi que le même tableau sert au catalogue
(`is_basket = false`) et au panier (`is_basket = true`, avec
`items = basket.items`).

**`{% macro %}`** est une fonction avec des paramètres explicites:

```jinja
{% macro render_field(field, placeholder='') %}
    <div class="mb-3">
        {{ field.label(class="form-label") }}
        {{ field(class="form-control" + (" is-invalid" if field.errors else ""),
                 placeholder=placeholder or field.label.text) }}
        {% for error in field.errors %}
            <div class="invalid-feedback">{{ error }}</div>
        {% endfor %}
    </div>
{% endmacro %}
```

```jinja
{% from "macros/form_macros.html" import render_field %}
{{ render_field(form.username) }}
```

Préférez la macro dès qu'il y a des paramètres: les dépendances sont visibles
dans la signature, alors qu'un `include` dépend de variables « ambiantes »
faciles à casser.

## Les objets WTForms dans un template

```jinja
{{ form.hidden_tag() }}                  {# tous les champs cachés, dont le CSRF #}
{{ form.username.label }}                {# <label for="username">...</label> #}
{{ form.username }}                      {# <input id="username" name="username" ...> #}
{{ form.username(class="form-control") }} {# les kwargs deviennent des attributs HTML #}
{{ form.username.errors }}               {# la liste des messages #}
```

Appeler le champ (`form.username(...)`) génère la balise adaptée au type de champ
— `input`, `textarea`, `select` — avec la valeur courante. On n'écrit donc jamais
les `<input>` à la main, sinon la valeur ne serait pas réaffichée après une erreur
de validation.

## Variables disponibles partout

Sans qu'aucun controller ne les passe:

| Variable | Source |
|---|---|
| `current_user` | le `@app.context_processor` de `app/__init__.py` |
| `request`, `session`, `config`, `g` | Flask |
| `url_for()`, `get_flashed_messages()` | Flask |
| `csrf_token()` | `CSRFProtect` |

Le *context processor*:

```python
@app.context_processor
def inject_current_user():
    ...
    return {'current_user': auth_service.get_current_user()}
```

Le dictionnaire retourné est fusionné avec les variables de **chaque** rendu. Sans
lui, il faudrait passer `current_user=...` dans les quinze `render_template` du
projet.

## Filtres

```jinja
{{ item.description | truncate(60) }}      coupe proprement
{{ user.role_names() | join(', ') }}       joint une liste
{{ nom | upper }} {{ nom | lower }} {{ nom | capitalize }}
{{ valeur | default('-') }}                si undefined
{{ prix | round(2) }}
{{ liste | length }}
{{ texte | safe }}                         DÉSACTIVE l'échappement (danger, voir plus bas)
```

Un filtre s'applique avec `|` et s'enchaîne:
`{{ description | truncate(40) | upper }}`.

## Structures de contrôle

```jinja
{% if items %}...{% elif autre %}...{% else %}...{% endif %}

{% for item in items %}
    {{ loop.index }}  {# 1, 2, 3... ; loop.index0 commence à 0 #}
    {{ loop.first }} {{ loop.last }} {{ loop.length }}
{% else %}
    {# exécuté si la liste est vide: pratique, et propre à Jinja #}
{% endfor %}
```

Les expressions conditionnelles fonctionnent comme en Python:

```jinja
{{ 'Quantité' if is_basket else 'Stock' }}
<span class="badge bg-{{ 'success' if item.stock > 0 else 'secondary' }}">
```

Tests utiles: `{% if item is none %}`, `{% if x is defined %}`,
`{% if n is divisibleby 3 %}`. Et `~` concatène:
`{{ 'Modifier « ' ~ item.name ~ ' »' }}`.

## Échappement automatique (XSS)

Jinja échappe **par défaut** toutes les variables. Si une description contient
`<script>alert(1)</script>`, elle s'affiche comme du texte au lieu d'être
exécutée. C'est la protection contre les failles **XSS**.

Le filtre `| safe` désactive cette protection. Ne l'utilisez que sur du HTML dont
**vous** êtes l'auteur, jamais sur une donnée saisie par un utilisateur ou venant
de la base. Même remarque pour `Markup(...)` côté Python.

## Ce que le template ne doit pas faire

- **pas de requête** ni d'accès à `db.session` — les données arrivent en DTO,
  déjà chargées;
- **pas de décision de sécurité** — `{% if current_user.is_admin() %}` cache un
  lien, il ne protège pas une route (voir
  [09-authentification.md](09-authentification.md));
- **pas de logique métier** — si un template calcule un total, la méthode
  manque au DTO (`basket.total_quantity()`).

## Fichiers statiques

```jinja
<link href="{{ url_for('static', filename='css/app.css') }}" rel="stylesheet">
```

Flask sert automatiquement `app/static/`. Ce projet charge Bootstrap depuis un CDN
pour rester léger; en production on préfère souvent servir ses propres fichiers
(pas de dépendance externe, pas de fuite d'adresses IP vers un tiers).
