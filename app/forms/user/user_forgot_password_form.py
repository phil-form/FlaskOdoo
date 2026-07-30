from flask_wtf import FlaskForm
from wtforms import EmailField
from wtforms.validators import DataRequired, Email


class UserForgotPasswordForm(FlaskForm):
    """« J'ai oublié mon mot de passe »: on ne demande que l'adresse email.

    Aucun validator ne vérifie que l'adresse EXISTE en base, et c'est
    volontaire: un message « cette adresse est inconnue » permettrait de
    découvrir qui a un compte sur le site. Le controller répond donc toujours la
    même chose, que le mail soit envoyé ou non.
    """

    email = EmailField('Email', validators=[DataRequired(), Email()])
