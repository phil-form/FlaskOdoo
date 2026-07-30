from flask_wtf import FlaskForm
from wtforms import EmailField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional

from app.services.role_service import RoleService


class UserUpdateForm(FlaskForm):
    """Modification d'un profil (email, description, et rôles pour un admin).

    Le champ userroles est un SelectMultipleField: WTForms REFUSE toute valeur
    qui n'est pas dans `choices`. C'est ce qui empêche un utilisateur malin de
    poster `roles=42` pour s'inventer un rôle inexistant. On remplit donc les
    choices dynamiquement depuis la base, dans __init__.

    coerce=int: les valeurs arrivent en texte depuis HTTP, on les convertit en
    entier pour pouvoir les comparer aux role_id.
    """

    email = EmailField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=255)])
    roles = SelectMultipleField('Rôles', coerce=int, validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.role_service = RoleService()
        # choices = liste de tuples (valeur postée, libellé affiché)
        self.roles.choices = [(role.role_id, role.role_name)
                              for role in self.role_service.find_all_entities()]

    def selected_roles(self):
        """Les entités Role cochées dans le formulaire."""
        return [self.role_service.find_one_entity(role_id)
                for role_id in (self.roles.data or [])]
