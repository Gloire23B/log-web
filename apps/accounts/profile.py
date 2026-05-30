"""
apps/accounts/profile.py
─────────────────────────────────────────────────────────────────
Page Profil utilisateur : modifier ses informations,
changer son mot de passe, gérer ses préférences de notification.
"""

from django import forms
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import UpdateView
from django.urls import reverse_lazy

User = get_user_model()


class ProfileForm(forms.ModelForm):
    """Formulaire de mise à jour du profil utilisateur."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "timezone",
                  "notify_on_error", "notify_on_warning", "avatar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_cls = (
            "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-2.5 "
            "text-[#E6EDF3] text-sm placeholder-[#484F58] "
            "focus:outline-none focus:border-[#388BFD] focus:ring-1 focus:ring-[#388BFD] "
            "transition-colors"
        )
        checkbox_cls = "w-4 h-4 rounded border-[#30363D] bg-[#0D1117] text-[#388BFD]"
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = checkbox_cls
            elif not isinstance(field.widget, forms.FileInput):
                field.widget.attrs["class"] = input_cls


class PasswordChangeForm(forms.Form):
    """Formulaire de changement de mot de passe."""
    current_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput(attrs={
            "class": "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-2.5 "
                     "text-[#E6EDF3] text-sm focus:outline-none focus:border-[#388BFD] "
                     "focus:ring-1 focus:ring-[#388BFD] transition-colors",
        })
    )
    new_password = forms.CharField(
        label="Nouveau mot de passe",
        min_length=8,
        widget=forms.PasswordInput(attrs={
            "class": "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-2.5 "
                     "text-[#E6EDF3] text-sm focus:outline-none focus:border-[#388BFD] "
                     "focus:ring-1 focus:ring-[#388BFD] transition-colors",
        })
    )
    confirm_password = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={
            "class": "w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-2.5 "
                     "text-[#E6EDF3] text-sm focus:outline-none focus:border-[#388BFD] "
                     "focus:ring-1 focus:ring-[#388BFD] transition-colors",
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pwd = self.cleaned_data["current_password"]
        if not self.user.check_password(pwd):
            raise forms.ValidationError("Mot de passe actuel incorrect.")
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les nouveaux mots de passe ne correspondent pas.")
        return cleaned


class ProfileView(LoginRequiredMixin, UpdateView):
    """Vue principale du profil — mise à jour des informations personnelles."""
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")
    login_url = "/auth/login/"

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Profil — LogMonitor"
        ctx["password_form"] = PasswordChangeForm(user=self.request.user)
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Profil mis à jour avec succès.")
        return super().form_valid(form)


class PasswordChangeView(LoginRequiredMixin, UpdateView):
    """Traitement du changement de mot de passe (POST uniquement)."""
    login_url = "/auth/login/"

    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            # Maintenir la session après changement de mot de passe
            update_session_auth_hash(request, request.user)
            messages.success(request, "Mot de passe modifié avec succès.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        from django.shortcuts import redirect
        return redirect("accounts:profile")
