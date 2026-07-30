from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class UserRegisterForm(FlaskForm):
    """Formulaire d'inscription.

    FlaskForm (flask-wtf) ajoute deux choses à WTForms:
    - la lecture automatique de request.form (pas besoin de passer les données)
    - un champ CSRF caché, signé avec app.secret_key, rendu par
      form.hidden_tag() dans le template. Sans lui, form.validate_on_submit()
      refuse le POST: c'est la protection contre les formulaires soumis depuis
      un autre site.

    Les validators sont le seul endroit où l'on définit les règles: le HTML
    (`required`) est du confort utilisateur, il est trivialement contournable.
    """

    username = StringField('Nom d\'utilisateur',
                           validators=[DataRequired(), Length(min=3, max=80)])
    email = EmailField('Email',
                       validators=[DataRequired(), Email(), Length(max=120)])
    # PasswordField = StringField dont la valeur n'est pas réaffichée.
    # Length(min=4): volontairement souple pour la formation. La dernière étape
    # rend cette règle dépendante de l'environnement (souple en debug, stricte
    # en production).
    password = PasswordField('Mot de passe',
                             validators=[DataRequired(), Length(min=4, max=128),
                                         EqualTo('confirm',
                                                 message='Les mots de passe ne correspondent pas!')])
    confirm = PasswordField('Confirmation', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=255)])
