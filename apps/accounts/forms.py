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

TIMEZONE_CHOICES = [
    ("UTC", "UTC (UTC+0)"),
    ("Europe/Paris", "Europe/Paris (UTC+1/+2)"),
    ("Europe/London", "Europe/London (UTC+0/+1)"),
    ("Europe/Berlin", "Europe/Berlin (UTC+1/+2)"),
    ("Europe/Madrid", "Europe/Madrid (UTC+1/+2)"),
    ("Europe/Rome", "Europe/Rome (UTC+1/+2)"),
    ("Europe/Brussels", "Europe/Brussels (UTC+1/+2)"),
    ("Europe/Amsterdam", "Europe/Amsterdam (UTC+1/+2)"),
    ("Africa/Kinshasa", "Africa/Kinshasa (UTC+1)"),
    ("Africa/Lubumbashi", "Africa/Lubumbashi (UTC+2)"),
    ("Africa/Nairobi", "Africa/Nairobi (UTC+3)"),
    ("Africa/Lagos", "Africa/Lagos (UTC+1)"),
    ("Africa/Dakar", "Africa/Dakar (UTC+0)"),
    ("Africa/Casablanca", "Africa/Casablanca (UTC+1)"),
    ("America/New_York", "America/New_York (UTC-5/-4)"),
    ("America/Chicago", "America/Chicago (UTC-6/-5)"),
    ("America/Los_Angeles", "America/Los_Angeles (UTC-8/-7)"),
    ("America/Sao_Paulo", "America/Sao_Paulo (UTC-3)"),
    ("Asia/Dubai", "Asia/Dubai (UTC+4)"),
    ("Asia/Kolkata", "Asia/Kolkata (UTC+5:30)"),
    ("Asia/Shanghai", "Asia/Shanghai (UTC+8)"),
    ("Asia/Tokyo", "Asia/Tokyo (UTC+9)"),
    ("Australia/Sydney", "Australia/Sydney (UTC+10/+11)"),
]


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


class RegisterForm(forms.Form):
    """Formulaire d'inscription — crée un compte avec le rôle Utilisateur."""

    first_name = forms.CharField(
        label=_("Prénom"),
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Jean",
            "autocomplete": "given-name",
        }),
    )
    last_name = forms.CharField(
        label=_("Nom"),
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Dupont",
            "autocomplete": "family-name",
        }),
    )
    email = forms.EmailField(
        label=_("Adresse email"),
        widget=forms.EmailInput(attrs={
            "placeholder": "jean.dupont@exemple.com",
            "autocomplete": "email",
        }),
    )
    timezone = forms.ChoiceField(
        label=_("Fuseau horaire"),
        choices=TIMEZONE_CHOICES,
        initial="Europe/Paris",
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "placeholder": "••••••••",
            "autocomplete": "new-password",
        }),
    )
    confirm_password = forms.CharField(
        label=_("Confirmer le mot de passe"),
        widget=forms.PasswordInput(attrs={
            "placeholder": "••••••••",
            "autocomplete": "new-password",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_cls = (
            "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-3 "
            "text-[#E6EDF3] placeholder-[#484F58] text-sm "
            "focus:outline-none focus:border-[#388BFD] focus:ring-1 focus:ring-[#388BFD] "
            "transition-colors duration-200"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", input_cls)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("Un compte avec cet email existe déjà."))
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        user = User(
            username=email,
            email=email,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            timezone=self.cleaned_data["timezone"],
            role=User.Role.USER,
        )
        user.set_password(self.cleaned_data["password"])
        user.save()
        return user


INPUT_CLS = (
    "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-2.5 "
    "text-[#E6EDF3] placeholder-[#484F58] text-sm "
    "focus:outline-none focus:border-[#388BFD] focus:ring-1 focus:ring-[#388BFD] "
    "transition-colors duration-200"
)
CHECKBOX_CLS = "w-4 h-4 rounded border-[#30363D] bg-[#0D1117] text-[#388BFD] focus:ring-[#388BFD] focus:ring-offset-0"


class UserAdminCreateForm(forms.Form):
    """Formulaire de création d'utilisateur par l'administrateur."""

    first_name = forms.CharField(label=_("Prénom"), max_length=150, widget=forms.TextInput(attrs={"placeholder": "Jean"}))
    last_name = forms.CharField(label=_("Nom"), max_length=150, widget=forms.TextInput(attrs={"placeholder": "Dupont"}))
    email = forms.EmailField(label=_("Adresse email"), widget=forms.EmailInput(attrs={"placeholder": "jean.dupont@exemple.com"}))
    timezone = forms.ChoiceField(label=_("Fuseau horaire"), choices=TIMEZONE_CHOICES, initial="Europe/Paris")
    role = forms.ChoiceField(label=_("Rôle"), choices=User.Role.choices, initial=User.Role.USER)
    password = forms.CharField(label=_("Mot de passe"), min_length=8, widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}))
    confirm_password = forms.CharField(label=_("Confirmer le mot de passe"), widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLS)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("Un compte avec cet email existe déjà."))
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        user = User(
            username=email,
            email=email,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            timezone=self.cleaned_data["timezone"],
            role=self.cleaned_data["role"],
        )
        user.set_password(self.cleaned_data["password"])
        user.save()
        return user


class UserAdminEditForm(forms.ModelForm):
    """Formulaire d'édition d'utilisateur par l'administrateur."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "timezone", "role", "is_active"]

    def __init__(self, *args, protected=False, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = CHECKBOX_CLS
            else:
                field.widget.attrs.setdefault("class", INPUT_CLS)
        if protected:
            self.fields["role"].disabled = True

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Un compte avec cet email existe déjà."))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        if commit:
            user.save()
        return user
