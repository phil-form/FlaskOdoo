from flask import jsonify, request
from werkzeug.datastructures import MultiDict

from app.dtos.abstract_dto import AbstractDTO

# Taille de page par défaut et plafond. Le plafond n'est pas décoratif: sans
# lui, `?per_page=1000000` est un déni de service en une requête, offert par
# l'API elle-même.
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


def json_ok(payload=None, status: int = 200, **extra):
    """Réponse de succès.

    `payload` peut être un DTO, une liste de DTO, un dict ou une liste de dicts:
    la conversion passe par `get_json_parsable()`, la méthode qu'AbstractDTO
    impose depuis l'étape 04. Elle n'avait jamais servi — l'API est la raison
    pour laquelle elle existait.
    """
    corps = extra

    if payload is not None:
        corps['data'] = to_json(payload)

    return jsonify(corps), status


def json_error(message: str, status: int, **extra):
    """Réponse d'erreur, toujours de la même forme.

    Un client d'API doit pouvoir traiter les erreurs sans lire la documentation
    page par page: une seule enveloppe (`error`, `status`), et le détail dans
    des champs optionnels. Le pire format d'erreur est celui qui change d'une
    route à l'autre.
    """
    return jsonify({'error': message, 'status': status, **extra}), status


def to_json(valeur):
    """DTO -> dict, liste de DTO -> liste de dicts, le reste tel quel."""
    if isinstance(valeur, AbstractDTO):
        return valeur.get_json_parsable()

    if isinstance(valeur, (list, tuple)):
        return [to_json(element) for element in valeur]

    return valeur


def pagination_args() -> tuple[int, int]:
    """(page, per_page) lus dans la query string, bornés.

    `type=int` de `request.args.get` renvoie None si la valeur n'est pas un
    entier — `?page=abc` ne doit pas produire une erreur 500. On borne ensuite:
    une page négative n'a pas de sens, et per_page est plafonné.
    """
    page = request.args.get('page', 1, type=int) or 1
    per_page = request.args.get('per_page', DEFAULT_PER_PAGE, type=int) or DEFAULT_PER_PAGE

    return max(1, page), max(1, min(per_page, MAX_PER_PAGE))


def paginate(elements: list, page: int, per_page: int):
    """Découpe une liste déjà chargée, et rend l'enveloppe de pagination.

    ATTENTION, limite assumée: on pagine **en Python**, après avoir tout chargé
    depuis la base. C'est honnête sur un catalogue de démonstration, et faux dès
    que la table est grosse: la vraie pagination se fait en SQL
    (`LIMIT`/`OFFSET`, ou mieux, un curseur sur une colonne indexée).

    Le garder ainsi est un choix pédagogique — la structure de la réponse est le
    sujet du chapitre, pas l'optimisation. Le corriger est un exercice, et le
    commentaire est là pour que personne ne copie ce code en production sans
    savoir ce qu'il copie.
    """
    total = len(elements)
    debut = (page - 1) * per_page

    return elements[debut:debut + per_page], {
        'page': page,
        'per_page': per_page,
        'total': total,
        # Division entière arrondie au supérieur, sans importer math.
        'pages': (total + per_page - 1) // per_page,
    }


def form_errors(form) -> dict:
    """Les erreurs WTForms, prêtes pour du JSON.

    `form.errors` contient déjà {champ: [messages]}. On le recopie pour ne pas
    exposer d'objet WTForms, et pour que le format reste stable si la
    bibliothèque change.
    """
    return {champ: list(messages) for champ, messages in form.errors.items()}


def to_formdata(payload: dict) -> MultiDict:
    """Transforme un corps JSON en `formdata` WTForms — en CHAÎNES.

    Le détail qui coûte une heure si on l'ignore: WTForms distingue `data`
    (une valeur par défaut posée par le programme) et `formdata` (une saisie
    reçue). Plusieurs validators ne regardent que `field.raw_data`, qui n'est
    rempli que par `formdata`; avec `data=`, ils concluent « champ absent ».

    Et il ne suffit pas de passer un MultiDict: il faut passer des **chaînes**.
    `InputRequired` teste littéralement `if field.raw_data and
    field.raw_data[0]`. Avec l'entier `0` de JSON, c'est faux, et le champ est
    déclaré manquant. Un navigateur, lui, envoie la chaîne `"0"` — qui est
    vraie. Sans conversion, l'API refuserait toute création d'article avec un
    stock à zéro, avec un message d'erreur qui accuse un champ pourtant fourni.

    C'est le troisième avatar du même piège dans ce projet (voir `DataRequired`
    vs `InputRequired` à l'étape 04): **zéro n'est pas l'absence de valeur**, et
    tout code qui teste la vérité d'une valeur numérique se trompe tôt ou tard.

    Les booléens JSON sont traduits en convention HTML (`'y'` / champ absent):
    une case non cochée n'est pas envoyée, elle ne vaut pas `"False"` — qui
    serait une chaîne non vide, donc vraie.
    """
    formdata = MultiDict()

    for cle, valeur in payload.items():
        if valeur is None:
            continue

        if isinstance(valeur, bool):
            if valeur:
                formdata.add(cle, 'y')
            continue

        if isinstance(valeur, (list, tuple)):
            # Un champ à valeurs multiples (SelectMultipleField): plusieurs
            # entrées sous la même clé, comme le ferait un navigateur.
            for element in valeur:
                formdata.add(cle, str(element))
            continue

        formdata.add(cle, str(valeur))

    return formdata


def json_body() -> dict:
    """Le corps JSON de la requête, ou {} — jamais une exception.

    `request.get_json()` lève un 400 brut (page HTML) si le corps n'est pas du
    JSON valide ou si le Content-Type ne convient pas. Une API ne doit jamais
    répondre du HTML: on récupère la main ici pour produire une erreur de la
    bonne forme.
    """
    donnees = request.get_json(silent=True)

    return donnees if isinstance(donnees, dict) else {}
