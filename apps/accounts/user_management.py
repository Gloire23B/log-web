"""
apps/accounts/user_management.py
─────────────────────────────────────────────────────────────────
Vues de gestion des comptes utilisateurs (réservé aux admins).
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import TIMEZONE_CHOICES, UserAdminCreateForm, UserAdminEditForm
from .mixins import AdminOnlyMixin

User = get_user_model()

PROTECTED_USERNAME = "admin"


def _list_context(request, create_form=None, create_modal_open=False):
    users = User.objects.all().order_by("-date_joined")
    return {
        "page_title": "Utilisateurs — LogMonitor",
        "page_heading": "Gestion des utilisateurs",
        "users": users,
        "create_form": create_form or UserAdminCreateForm(),
        "create_modal_open": create_modal_open,
        "role_choices": User.Role.choices,
        "timezone_choices": TIMEZONE_CHOICES,
        "PROTECTED_USERNAME": PROTECTED_USERNAME,
        "total_count": users.count(),
        "admin_count": users.filter(role="admin").count(),
        "user_count": users.filter(role="user").count(),
        "other_count": users.exclude(role__in=["admin", "user"]).count(),
    }


class UserListView(AdminOnlyMixin, LoginRequiredMixin, View):
    template_name = "accounts/users.html"
    login_url = "/auth/login/"

    def get(self, request):
        return render(request, self.template_name, _list_context(request))


class UserCreateView(AdminOnlyMixin, LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request):
        form = UserAdminCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Utilisateur {user.display_name} créé avec succès.")
            return redirect("accounts:user_list")
        return render(request, "accounts/users.html", _list_context(request, create_form=form, create_modal_open=True))


class UserEditView(AdminOnlyMixin, LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        protected = (user.username == PROTECTED_USERNAME)
        form = UserAdminEditForm(request.POST, instance=user, protected=protected)
        if form.is_valid():
            form.save()
            messages.success(request, f"Utilisateur {user.display_name} modifié avec succès.")
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
        return redirect("accounts:user_list")


class UserDeleteView(AdminOnlyMixin, LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.username == PROTECTED_USERNAME:
            messages.error(request, "Le compte administrateur par défaut ne peut pas être supprimé.")
            return redirect("accounts:user_list")
        if user.pk == request.user.pk:
            messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
            return redirect("accounts:user_list")
        name = user.display_name
        user.delete()
        messages.success(request, f"Utilisateur {name} supprimé.")
        return redirect("accounts:user_list")


class UserBulkDeleteView(AdminOnlyMixin, LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request):
        ids = request.POST.getlist("user_ids")
        if not ids:
            messages.warning(request, "Aucun utilisateur sélectionné.")
            return redirect("accounts:user_list")
        qs = (
            User.objects.filter(pk__in=ids)
            .exclude(username=PROTECTED_USERNAME)
            .exclude(pk=request.user.pk)
        )
        count = qs.count()
        qs.delete()
        if count:
            messages.success(request, f"{count} utilisateur(s) supprimé(s).")
        else:
            messages.warning(request, "Aucun utilisateur éligible à la suppression dans la sélection.")
        return redirect("accounts:user_list")
