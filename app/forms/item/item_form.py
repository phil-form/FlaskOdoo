from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange


class ItemForm(FlaskForm):
    """Création ET modification d'un article: le même formulaire sert aux deux.

    En modification, le controller fait `ItemForm(obj=item)`: WTForms recopie
    les attributs de l'objet dans les champs de même nom, ce qui pré-remplit le
    formulaire sans une ligne de code.

    Détail important: InputRequired sur stock, pas DataRequired. DataRequired
    considère 0 comme "vide" (0 est falsy en Python) et refuserait un stock
    à zéro. InputRequired ne vérifie que la présence du champ.
    """

    name = StringField('Nom', validators=[DataRequired(), Length(min=2, max=255)])
    description = TextAreaField('Description', validators=[DataRequired()])
    stock = IntegerField('Stock', validators=[InputRequired(), NumberRange(min=0)])
