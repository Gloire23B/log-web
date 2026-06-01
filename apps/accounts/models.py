"""
apps/accounts/models.py
─────────────────────────────────────────────────────────────────
Modèle utilisateur personnalisé avec gestion des rôles (RBAC).
Hérite de AbstractUser pour bénéficier du système d'auth Django.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Utilisateur personnalisé LogMonitor.
    Étend AbstractUser avec :
    - Rôles (RBAC) : admin, analyst, viewer
    - Avatar
    - Préférences de notifications
    """

    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrateur")
        ANALYST = "analyst", _("Analyste")
        VIEWER = "viewer", _("Lecteur")
        USER = "user", _("Utilisateur")

    # Rôle de l'utilisateur — contrôle les permissions dans l'UI
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
        verbose_name=_("Rôle"),
    )

    # Avatar optionnel
    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        verbose_name=_("Avatar"),
    )

    # Préférences de notifications par email
    notify_on_error = models.BooleanField(
        default=True,
        verbose_name=_("Notifier sur erreur critique"),
    )
    notify_on_warning = models.BooleanField(
        default=False,
        verbose_name=_("Notifier sur avertissement"),
    )

    # Timezone de l'utilisateur (affichage des logs)
    timezone = models.CharField(
        max_length=50,
        default="Europe/Paris",
        verbose_name=_("Fuseau horaire"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_user(self):
        """Vérifie si l'utilisateur a le rôle administrateur."""
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def can_manage_logs(self):
        """Analyste et Admin peuvent gérer les logs."""
        return self.role in (self.Role.ADMIN, self.Role.ANALYST)

    @property
    def display_name(self):
        """Nom d'affichage avec fallback sur username."""
        return self.get_full_name() or self.username

    @property
    def initials(self):
        """Initiales pour l'avatar généré."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.username[:2].upper()
