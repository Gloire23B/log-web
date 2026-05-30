"""
apps/accounts/forms.py
─────────────────────────────────────────────────────────────────
Formulaires d'authentification avec validation stricte.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class LoginForm(AuthenticationForm):
    """
    Formulaire de connexion personnalisé.
    Surcharge AuthenticationForm pour le styling Tailwind.
    """

    username = forms.CharField(
        label=_("Identifiant"),
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": (
                "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-3 "
                "text-[#E6EDF3] placeholder-[#484F58] text-sm "
                "focus:outline-none focus:border-[#388BFD] focus:ring-1 focus:ring-[#388BFD] "
                "transition-colors duration-200"
            ),
            "placeholder": "admin@logmonitor.io",
            "autocomplete": "username",
        }),
    )

    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            "class": (
                "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-3 "
                "text-[#E6EDF3] placeholder-[#484F58] text-sm "
                "focus:outline-none focus:border-[#388BFD] focus:ring-1 focus:ring-[#388BFD] "
                "transition-colors duration-200"
            ),
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )

    remember_me = forms.BooleanField(
        label=_("Se souvenir de moi"),
        required=False,
        widget=forms.CheckboxInput(attrs={
            "class": "w-4 h-4 rounded border-[#30363D] bg-[#0D1117] text-[#388BFD] "
                     "focus:ring-[#388BFD] focus:ring-offset-0",
        }),
    )

    error_messages = {
        "invalid_login": _(
            "Identifiant ou mot de passe incorrect. "
            "Attention : la vérification est sensible à la casse."
        ),
        "inactive": _("Ce compte est désactivé."),
    }
