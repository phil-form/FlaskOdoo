"""Controller "bac à sable" des premiers exercices Jinja2.

Il ne sert plus l'accueil (c'est home_controller qui a la route '/'), mais on
le garde: il montre le strict minimum d'une vue Flask, sans service ni base de
données.
"""
from flask import render_template

from app import app
from app.models.LiItem import LiItem


@app.get('/jinja')
def test():
    # LiItem n'est pas une entité: c'est un objet Python jetable, juste pour
    # avoir des données à boucler dans le template.
    items = [LiItem() for i in range(10)]

    return render_template('home/jinja.html',
                           ma_variable="Coucou",
                           items=items)


@app.get('/autre')
def test2():
    # Une vue peut aussi renvoyer directement une chaîne: Flask la transforme
    # en réponse HTTP 200 avec le content-type text/html.
    return """
    <h1>Mon autre page</h1>
    """
