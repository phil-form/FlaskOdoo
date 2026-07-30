"""Controller des utilisateurs: inscription, connexion, profils, admin.

Motif récurrent dans tout ce fichier, le "POST/Redirect/GET":

    @app.route('/truc', methods=['GET', 'POST'])
    def truc():
        form = TrucForm()
        if form.validate_on_submit():   # POST + CSRF + validators OK
            service.faire_le_travail(form)
            return redirect(url_for('autre_page'))   # <- redirection!
        return render_template('truc.html', form=form)   # GET, ou POST invalide

On REDIRIGE après un POST réussi au lieu de rendre directement le template.
Sinon, un F5 sur la page renvoie le formulaire une deuxième fois (double
inscription, double commande...) et le navigateur affiche un avertissement.
"""
from flask import flash, redirect, render_template, request, url_for

from app import app
from app.forms.user.user_forgot_password_form import UserForgotPasswordForm
from app.forms.user.user_login_form import UserLoginForm
from app.forms.user.user_register_form import UserRegisterForm
from app.forms.user.user_reset_password_form import UserResetPasswordForm
from app.forms.user.user_update_form import UserUpdateForm
from app.framework.decorators.auth_required import auth_required
from app.framework.decorators.inject import inject
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService
from app.services.password_reset_service import PasswordResetService
from app.services.user_service import UserService


# --- authentification -------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
@inject
def login(user_service: UserService, auth_service: AuthService):
    if auth_service.is_authenticated():
        return redirect(url_for('index'))

    form = UserLoginForm()

    # validate_on_submit() = "la requête est un POST ET le formulaire est
    # valide" (jeton CSRF inclus). C'est le seul test à écrire.
    if form.validate_on_submit():
        user = user_service.login(form)

        if user is not None:
            auth_service.login(user)
            flash(f"Bienvenue {user.username}!", "success")

            # ?next=/page/demandée déposé par @auth_required.
            # On vérifie que la cible est bien une URL interne: accepter
            # n'importe quoi ici, c'est offrir une redirection ouverte
            # (?next=https://site-pirate) très pratique pour du phishing.
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            return redirect(url_for('index'))

        # Message volontairement vague: on ne dit pas si c'est le nom ou le
        # mot de passe qui est faux.
        flash("Utilisateur ou mot de passe incorrect.", "danger")

    return render_template('users/login.html', form=form)


@app.get('/logout')
@inject
def logout(auth_service: AuthService):
    auth_service.logout()
    flash("Vous êtes déconnecté.", "info")

    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
@inject
def register(user_service: UserService, auth_service: AuthService,
             email_verification_service: EmailVerificationService):
    if auth_service.is_authenticated():
        return redirect(url_for('index'))

    form = UserRegisterForm()

    if form.validate_on_submit():
        user = user_service.insert(form)

        if user is None:
            flash("Ce nom d'utilisateur ou cet email est déjà utilisé.", "danger")
        else:
            # L'envoi du mail ne conditionne PAS la création du compte: si le
            # SMTP est en panne, le compte existe et le lien pourra être
            # redemandé. On ne perd pas une inscription pour un mail.
            email_verification_service.send_verification_link(user.user_id)

            flash("Compte créé. Un mail vous a été envoyé pour confirmer "
                  "votre adresse.", "success")
            return redirect(url_for('login'))

    return render_template('users/register.html', form=form)


# --- vérification de l'adresse email ---------------------------------------

@app.get('/email/verify/<token>')
@inject
def email_verify(token: str, email_verification_service: EmailVerificationService):
    """Le lien reçu par mail après l'inscription.

    Pas d'@auth_required: on doit pouvoir confirmer son adresse sans être
    connecté (le lien est ouvert depuis un client mail, dans un autre
    navigateur la plupart du temps). La preuve, c'est le token.
    """
    if email_verification_service.verify(token):
        flash("Adresse confirmée, merci! Vous pouvez vous connecter.", "success")
        return redirect(url_for('login'))

    flash("Ce lien de confirmation est invalide, expiré, ou déjà utilisé.",
          "danger")

    return redirect(url_for('index'))


@app.post('/email/verify/resend')
@auth_required()
@inject
def email_verify_resend(email_verification_service: EmailVerificationService,
                        auth_service: AuthService):
    """Renvoi du lien, depuis le bandeau affiché aux comptes non confirmés.

    En POST: c'est une action (elle envoie un mail), pas une page.
    """
    email_verification_service.send_verification_link(
        auth_service.get_current_user().user_id)

    # Message unique, y compris si l'adresse était déjà confirmée: cette route
    # ne doit pas devenir un moyen de sonder l'état des comptes.
    flash("Si votre adresse n'est pas encore confirmée, un nouveau lien vient "
          "d'être envoyé.", "info")

    return redirect(request.referrer or url_for('index'))


# --- mot de passe oublié ----------------------------------------------------

@app.route('/password/forgot', methods=['GET', 'POST'])
@inject
def password_forgot(password_reset_service: PasswordResetService,
                    auth_service: AuthService):
    if auth_service.is_authenticated():
        return redirect(url_for('index'))

    form = UserForgotPasswordForm()

    if form.validate_on_submit():
        password_reset_service.send_reset_link(form.email.data)

        # Message IDENTIQUE que l'adresse existe ou non, et on ignore
        # volontairement le retour du service. Dire « adresse inconnue »
        # transformerait cette page en outil pour savoir qui a un compte ici.
        flash("Si un compte existe pour cette adresse, un lien de "
              "réinitialisation vient d'être envoyé.", "info")

        return redirect(url_for('login'))

    return render_template('users/forgot_password.html', form=form)


@app.route('/password/reset/<token>', methods=['GET', 'POST'])
@inject
def password_reset(token: str, password_reset_service: PasswordResetService):
    """Le lien reçu par mail. Le token est dans l'URL, pas dans un champ."""
    user = password_reset_service.find_user(token)

    if user is None:
        flash("Ce lien est invalide, expiré ou déjà utilisé. "
              "Demandez-en un nouveau.", "danger")
        return redirect(url_for('password_forgot'))

    form = UserResetPasswordForm()

    if form.validate_on_submit():
        # Le service revalide le token: entre l'affichage du formulaire et
        # l'envoi, il a pu expirer ou être consommé ailleurs.
        if password_reset_service.reset(token, form.password.data):
            flash("Mot de passe mis à jour, vous pouvez vous connecter.", "success")
            return redirect(url_for('login'))

        flash("La réinitialisation a échoué, le lien n'est plus valide.", "danger")
        return redirect(url_for('password_forgot'))

    return render_template('users/reset_password.html', form=form, user=user)


# --- profils ----------------------------------------------------------------

@app.get('/users')
@auth_required(level="ADMIN")
@inject
def user_list(user_service: UserService):
    return render_template('users/list.html', users=user_service.find_all())


@app.get('/users/<int:user_id>')
@auth_required()
@inject
def user_profile(user_id: int, user_service: UserService):
    # <int:user_id> dans la route -> paramètre user_id de la fonction, déjà
    # converti en int par Flask (une URL /users/abc renvoie un 404).
    user = user_service.find_one(user_id)

    if user is None:
        # abort(404) serait plus correct HTTP, mais en MVC on préfère souvent
        # un message + redirection, plus agréable pour l'utilisateur.
        flash("Utilisateur introuvable.", "warning")
        return redirect(url_for('index'))

    return render_template('users/profile.html', user=user)


@app.get('/profile')
@auth_required()
@inject
def profile(auth_service: AuthService):
    """Raccourci vers son propre profil."""
    return redirect(url_for('user_profile',
                            user_id=auth_service.get_current_user().user_id))


@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@auth_required(or_is_current_user=True)
@inject
def user_update(user_id: int, user_service: UserService, auth_service: AuthService):
    """Modification d'un profil.

    or_is_current_user=True se lit: "le propriétaire de la ressource, ou un
    ADMIN" (un ADMIN passe partout). La vue doit avoir un paramètre `user_id`,
    et le décorateur le vérifie au démarrage.
    """
    user = user_service.find_one(user_id)

    if user is None:
        flash("Utilisateur introuvable.", "warning")
        return redirect(url_for('index'))

    # obj=user pré-remplit les champs de même nom en GET.
    form = UserUpdateForm(obj=user)
    current_user = auth_service.get_current_user()

    if form.validate_on_submit():
        updated = user_service.update(user_id, form)

        if updated is None:
            flash("Cet email est déjà utilisé.", "danger")
        else:
            # Les rôles ne sont appliqués que si l'auteur de la requête est
            # ADMIN. Le champ existe dans le formulaire pour tout le monde
            # (il est juste masqué dans le template), il ne faut donc pas se
            # contenter de le cacher côté HTML: on refait la vérification ici.
            if current_user.is_admin():
                user_service.update_roles(user_id, form.selected_roles())

            flash("Profil mis à jour.", "success")
            return redirect(url_for('user_profile', user_id=user_id))

    # En GET, cocher les rôles actuels dans le <select multiple>.
    if request.method == 'GET':
        form.roles.data = [role.role_id for role in user.roles]

    return render_template('users/update.html', form=form, user=user)


@app.post('/users/<int:user_id>/delete')
@auth_required(level="ADMIN")
@inject
def user_delete(user_id: int, user_service: UserService, auth_service: AuthService):
    """Désactive un compte (soft delete).

    En POST et pas en GET: une action qui modifie l'état ne doit jamais être
    accessible par un simple lien. Un <img src="/users/1/delete"> dans un mail
    suffirait à déclencher la suppression, et les navigateurs préchargent les
    liens.
    """
    if auth_service.get_current_user().user_id == user_id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "warning")
        return redirect(url_for('user_list'))

    if user_service.delete(user_id) is None:
        flash("Suppression impossible.", "danger")
    else:
        flash("Utilisateur désactivé.", "success")

    return redirect(url_for('user_list'))
