from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp

from app import app

# Règles de mot de passe: souples en debug, strictes en production.
#
# Une ternaire, évaluée UNE FOIS à l'import du module (app.debug est déjà défini
# à ce moment-là, voir l'ordre de app/__init__.py). En formation on tape
# « admin » cinquante fois par jour, il serait absurde d'exiger 12 caractères;
# en production l'inverse est vrai.
#
# Le piège à éviter serait de mettre ce genre de test DANS un validator appelé à
# chaque requête: ici la liste est construite au démarrage, il n'y a aucun coût
# ni aucune ambiguïté sur les règles appliquées.
#
# Les mêmes règles servent au formulaire de réinitialisation (voir
# user_reset_password_form.py): un mot de passe changé par mail doit être aussi
# solide qu'un mot de passe choisi à l'inscription.
PASSWORD_VALIDATORS = (
    # DEBUG: 4 caractères, on ne veut pas ralentir les exercices.
    [DataRequired(), Length(min=4, max=128)]
    if app.debug else
    # PRODUCTION: 12 caractères minimum, avec minuscule, majuscule et chiffre.
    # Regexp utilise re.match: les (?=...) sont des "lookahead", ils vérifient la
    # présence de chaque catégorie sans consommer de caractère.
    [DataRequired(), Length(min=12, max=128),
     Regexp(r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)',
            message="Le mot de passe doit contenir au moins une minuscule, "
                    "une majuscule et un chiffre.")]
)


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
    # *PASSWORD_VALIDATORS déballe la liste choisie par la ternaire ci-dessus,
    # et on y ajoute la comparaison avec le champ de confirmation.
    password = PasswordField('Mot de passe',
                             validators=[*PASSWORD_VALIDATORS,
                                         EqualTo('confirm',
                                                 message='Les mots de passe ne correspondent pas!')])
    confirm = PasswordField('Confirmation', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=255)])
