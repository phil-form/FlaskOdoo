from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired


class UserLoginForm(FlaskForm):
    """Formulaire de connexion.

    Volontairement sans validator de longueur ou de format: on ne donne aucune
    indication sur ce qui existe en base. Le message d'erreur est toujours le
    même ("utilisateur ou mot de passe incorrect"), sinon on permet d'énumérer
    les comptes existants.
    """

    username = StringField('Nom d\'utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
