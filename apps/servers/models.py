"""
apps/servers/models.py
─────────────────────────────────────────────────────────────────
Modèle Server : représente un nœud d'infrastructure physique ou VM.
Stocke les dernières métriques connues (CPU, RAM, Disk)
et le statut de santé calculé.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Server(models.Model):
    """
    Serveur physique ou virtuel de l'infrastructure.
    Les métriques sont mises à jour par l'agent de monitoring
    via l'API d'ingestion.
    """

    class Status(models.TextChoices):
        ONLINE  = "online",  _("En ligne")
        OFFLINE = "offline", _("Hors ligne")
        WARNING = "warning", _("Avertissement")
        CRITICAL = "critical", _("Critique")
        UNKNOWN  = "unknown",  _("Inconnu")

    class Environment(models.TextChoices):
        PRODUCTION  = "production",  _("Production")
        STAGING     = "staging",     _("Staging")
        DEVELOPMENT = "development", _("Développement")
        DR          = "dr",          _("Disaster Recovery")

    # ── Identification ────────────────────────────────────────────────
    name        = models.CharField(max_length=100, unique=True, verbose_name=_("Nom"), db_index=True)
    hostname    = models.CharField(max_length=255, blank=True, verbose_name=_("Hostname"))
    ip_address  = models.GenericIPAddressField(null=True, blank=True, verbose_name=_("Adresse IP"))
    environment = models.CharField(max_length=15, choices=Environment.choices,
                                   default=Environment.PRODUCTION, verbose_name=_("Environnement"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    tags        = models.JSONField(default=list, blank=True, verbose_name=_("Tags"))

    # ── Statut ────────────────────────────────────────────────────────
    status          = models.CharField(max_length=10, choices=Status.choices,
                                       default=Status.UNKNOWN, verbose_name=_("Statut"), db_index=True)
    last_seen       = models.DateTimeField(null=True, blank=True, verbose_name=_("Dernière activité"))
    is_active       = models.BooleanField(default=True, verbose_name=_("Actif"))

    # ── Métriques (dernière valeur connue) ────────────────────────────
    cpu_percent     = models.FloatField(null=True, blank=True, verbose_name=_("CPU (%)"))
    memory_percent  = models.FloatField(null=True, blank=True, verbose_name=_("RAM (%)"))
    disk_percent    = models.FloatField(null=True, blank=True, verbose_name=_("Disque (%)"))
    load_average    = models.FloatField(null=True, blank=True, verbose_name=_("Load average"))
    uptime_seconds  = models.BigIntegerField(null=True, blank=True, verbose_name=_("Uptime (s)"))

    # ── Source de logs associée (optionnel) ───────────────────────────
    log_source = models.OneToOneField(
        "logs.LogSource",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="server",
        verbose_name=_("Source de logs"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Serveur")
        verbose_name_plural = _("Serveurs")
        ordering = ["environment", "name"]

    def __str__(self):
        return f"{self.name} ({self.ip_address or self.hostname})"

    @property
    def status_color(self):
        """Classes CSS Tailwind selon le statut."""
        return {
            self.Status.ONLINE:   "text-emerald-400 bg-emerald-950 border-emerald-800",
            self.Status.WARNING:  "text-amber-400 bg-amber-950 border-amber-800",
            self.Status.CRITICAL: "text-red-400 bg-red-950 border-red-800",
            self.Status.OFFLINE:  "text-slate-500 bg-slate-900 border-slate-700",
            self.Status.UNKNOWN:  "text-slate-400 bg-slate-800 border-slate-700",
        }.get(self.status, "text-slate-400 bg-slate-800 border-slate-700")

    @property
    def status_dot(self):
        return {
            self.Status.ONLINE:   "bg-emerald-400",
            self.Status.WARNING:  "bg-amber-400 animate-pulse",
            self.Status.CRITICAL: "bg-red-400 animate-pulse",
            self.Status.OFFLINE:  "bg-slate-600",
            self.Status.UNKNOWN:  "bg-slate-500",
        }.get(self.status, "bg-slate-500")

    @property
    def cpu_color(self):
        if self.cpu_percent is None: return "bg-slate-600"
        if self.cpu_percent >= 90: return "bg-red-500"
        if self.cpu_percent >= 75: return "bg-amber-500"
        return "bg-emerald-500"

    @property
    def memory_color(self):
        if self.memory_percent is None: return "bg-slate-600"
        if self.memory_percent >= 90: return "bg-red-500"
        if self.memory_percent >= 80: return "bg-amber-500"
        return "bg-blue-500"

    @property
    def disk_color(self):
        if self.disk_percent is None: return "bg-slate-600"
        if self.disk_percent >= 90: return "bg-red-500"
        if self.disk_percent >= 75: return "bg-amber-500"
        return "bg-purple-500"

    @property
    def uptime_display(self):
        """Affiche l'uptime de façon lisible."""
        if not self.uptime_seconds:
            return "—"
        days = self.uptime_seconds // 86400
        hours = (self.uptime_seconds % 86400) // 3600
        if days > 0:
            return f"{days}j {hours}h"
        return f"{hours}h"

    def compute_status(self):
        """
        Calcule et met à jour le statut automatiquement
        en fonction des métriques actuelles.
        """
        if not self.last_seen:
            self.status = self.Status.UNKNOWN
            return

        age = (timezone.now() - self.last_seen).total_seconds()
        if age > 300:  # Plus de 5 minutes sans signal
            self.status = self.Status.OFFLINE
            return

        critical = (
            (self.cpu_percent or 0) >= 95 or
            (self.memory_percent or 0) >= 95 or
            (self.disk_percent or 0) >= 95
        )
        warning = (
            (self.cpu_percent or 0) >= 80 or
            (self.memory_percent or 0) >= 85 or
            (self.disk_percent or 0) >= 80
        )

        if critical:
            self.status = self.Status.CRITICAL
        elif warning:
            self.status = self.Status.WARNING
        else:
            self.status = self.Status.ONLINE
