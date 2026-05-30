"""
apps/alerts/models.py
─────────────────────────────────────────────────────────────────
Modèle d'alertes : règles de déclenchement et historique.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from apps.logs.models import LogSource, LogEntry

User = get_user_model()


class Alert(models.Model):
    """
    Alerte déclenchée automatiquement selon des règles de seuil.
    Exemples : > 50 erreurs en 5 minutes, CRITICAL détecté sur prod-server-01…
    """

    class Severity(models.TextChoices):
        LOW = "low", _("Faible")
        MEDIUM = "medium", _("Moyen")
        HIGH = "high", _("Élevé")
        CRITICAL = "critical", _("Critique")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        ACKNOWLEDGED = "acknowledged", _("Acquittée")
        RESOLVED = "resolved", _("Résolue")

    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MEDIUM,
        verbose_name=_("Sévérité"),
        db_index=True,
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("Statut"),
        db_index=True,
    )

    # Source concernée (optionnel)
    source = models.ForeignKey(
        LogSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        verbose_name=_("Source"),
    )

    # Log qui a déclenché l'alerte
    trigger_log = models.ForeignKey(
        LogEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_alerts",
        verbose_name=_("Log déclencheur"),
    )

    # Utilisateur ayant acquitté l'alerte
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
        verbose_name=_("Acquittée par"),
    )

    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Alerte")
        verbose_name_plural = _("Alertes")
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"

    @property
    def severity_color(self):
        return {
            self.Severity.LOW: "text-slate-400 bg-slate-800",
            self.Severity.MEDIUM: "text-amber-400 bg-amber-900/30",
            self.Severity.HIGH: "text-orange-400 bg-orange-900/30",
            self.Severity.CRITICAL: "text-red-400 bg-red-900/30",
        }.get(self.severity, "text-slate-400 bg-slate-800")
