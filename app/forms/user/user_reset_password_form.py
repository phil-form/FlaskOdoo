from flask_wtf import FlaskForm
from wtforms import PasswordField
from wtforms.validators import DataRequired, EqualTo

# On réutilise exactement les règles de l'inscription (souples en debug,
# strictes en prod): un mot de passe défini via un lien de réinitialisation doit
# être aussi solide qu'un mot de passe choisi à l'inscription. Les définir une
# seule fois évite qu'une des deux portes reste ouverte après une évolution.
from app.forms.user.user_register_form import PASSWORD_VALIDATORS


class UserResetPasswordForm(FlaskForm):
    """Choix du nouveau mot de passe, au bout du lien reçu par mail.

    Le token n'est PAS un champ du formulaire: il vient de l'URL
    (/password/reset/<token>). Le mettre dans un champ caché n'apporterait rien
    et le rendrait modifiable côté client.
    """

    password = PasswordField('Nouveau mot de passe',
                             validators=[*PASSWORD_VALIDATORS,
                                         EqualTo('confirm',
                                                 message='Les mots de passe ne correspondent pas!')])
    confirm = PasswordField('Confirmation', validators=[DataRequired()])
