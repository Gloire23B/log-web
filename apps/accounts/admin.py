"""
apps/accounts/admin.py
─────────────────────────────────────────────────────────────────
Configuration de l'interface d'administration Django.
Expose le modèle User personnalisé avec tous ses champs.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin du modèle User étendu."""

    list_display  = ("username", "email", "get_full_name", "role", "is_active", "date_joined")
    list_filter   = ("role", "is_active", "is_staff", "notify_on_error")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering      = ("-date_joined",)

    # Ajout des champs personnalisés dans le formulaire d'édition
    fieldsets = BaseUserAdmin.fieldsets + (
        (_("Rôle & Notifications"), {
            "fields": ("role", "avatar", "timezone", "notify_on_error", "notify_on_warning"),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_("Rôle"), {
            "fields": ("role",),
        }),
    )
