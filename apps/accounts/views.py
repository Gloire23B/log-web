"""
apps/accounts/views.py
─────────────────────────────────────────────────────────────────
Vues d'authentification (CBV).
- LoginView personnalisée avec gestion "remember me"
- LogoutView sécurisée (POST only)
"""

from django.contrib.auth import views as auth_views
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator

from .forms import LoginForm


@method_decorator(never_cache, name="dispatch")
class LoginView(auth_views.LoginView):
    """
    Vue de connexion personnalisée.
    - Utilise le formulaire LoginForm avec styling Tailwind
    - Gestion de l'option "remember me" (durée de session)
    - Redirige les utilisateurs déjà connectés
    """

    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        """
        Sur connexion valide :
        - Si "remember me" décoché → session expire à fermeture du navigateur
        - Si coché → session de 30 jours
        """
        remember_me = form.cleaned_data.get("remember_me", False)
        if not remember_me:
            # Session expire à la fermeture du navigateur
            self.request.session.set_expiry(0)
        else:
            # Session de 30 jours
            self.request.session.set_expiry(60 * 60 * 24 * 30)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Connexion — LogMonitor"
        return context


class LogoutView(auth_views.LogoutView):
    """
    Déconnexion sécurisée.
    Django 5+ : uniquement via POST pour éviter les CSRF logout attacks.
    """
    next_page = reverse_lazy("accounts:login")
