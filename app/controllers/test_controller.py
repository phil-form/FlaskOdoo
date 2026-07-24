from app import app
from app.models.LiItem import LiItem
from flask import render_template

@app.get('/')
def test():
    items = [LiItem() for i in range(10)]
    return render_template('home/home.html',
                           ma_variable="Coucou",
                           items=items)

@app.get('/autre')
def test2():
    return """
    <h1>Mon autre page</h1>
    """