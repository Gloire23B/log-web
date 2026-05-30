"""
apps/logs/models.py
─────────────────────────────────────────────────────────────────
Modèles centraux de l'application :
  • LogSource  → source émettrice d'un log (serveur, service, app)
  • LogEntry   → entrée de log individuelle
  • LogTag     → étiquette libre pour catégorisation

Index PostgreSQL sur les champs les plus filtrés (timestamp, level, source)
pour supporter un volume important de données.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class LogSource(models.Model):
    """
    Représente une source de logs (serveur, microservice, application…).
    Chaque LogEntry est rattachée à une source.
    """

    class SourceType(models.TextChoices):
        SERVER = "server", _("Serveur")
        SERVICE = "service", _("Service")
        APPLICATION = "application", _("Application")
        DATABASE = "database", _("Base de données")
        NETWORK = "network", _("Réseau")
        SECURITY = "security", _("Sécurité")

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Nom"),
        db_index=True,
    )
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.APPLICATION,
        verbose_name=_("Type"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    hostname = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Hostname / IP"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Source de logs")
        verbose_name_plural = _("Sources de logs")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"

    @property
    def recent_error_count(self):
        """Compte les erreurs des dernières 24h pour cette source."""
        since = timezone.now() - timezone.timedelta(hours=24)
        return self.log_entries.filter(
            level=LogEntry.Level.ERROR,
            timestamp__gte=since
        ).count()


class LogEntry(models.Model):
    """
    Entrée de log individuelle.

    Indexation PostgreSQL :
      - timestamp  → filtres temporels (le plus fréquent)
      - level      → filtres par niveau de sévérité
      - source     → filtres par source
      - (level, timestamp) → index composite pour requêtes combinées
    """

    class Level(models.TextChoices):
        DEBUG = "DEBUG", _("Debug")
        INFO = "INFO", _("Info")
        WARNING = "WARNING", _("Avertissement")
        ERROR = "ERROR", _("Erreur")
        CRITICAL = "CRITICAL", _("Critique")

    # ─── Champs principaux ────────────────────────────────────────────────────
    # Horodatage du log (fourni par la source, pas auto_now_add)
    timestamp = models.DateTimeField(
        verbose_name=_("Horodatage"),
        db_index=True,
    )

    # Niveau de sévérité — indexé pour filtres rapides
    level = models.CharField(
        max_length=10,
        choices=Level.choices,
        default=Level.INFO,
        verbose_name=_("Niveau"),
        db_index=True,
    )

    # Message principal du log
    message = models.TextField(verbose_name=_("Message"))

    # Source émettrice — FK avec index automatique
    source = models.ForeignKey(
        LogSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="log_entries",
        verbose_name=_("Source"),
        db_index=True,
    )

    # ─── Métadonnées enrichies ─────────────────────────────────────────────────
    # Nom du logger Python (ex: django.request, myapp.views)
    logger_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Logger"),
    )

    # Trace de la stack en cas d'erreur
    traceback = models.TextField(blank=True, verbose_name=_("Traceback"))

    # Données JSON supplémentaires (contexte, variables…)
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Données additionnelles"),
    )

    # Chemin du fichier source (ex: apps/views.py:42)
    file_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Fichier"),
    )

    # Numéro de ligne
    line_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Ligne"),
    )

    # Marqué comme résolu
    is_resolved = models.BooleanField(
        default=False,
        verbose_name=_("Résolu"),
    )

    # Date d'ingestion dans notre système
    ingested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Ingéré le"),
    )

    class Meta:
        verbose_name = _("Entrée de log")
        verbose_name_plural = _("Entrées de logs")
        ordering = ["-timestamp"]
        indexes = [
            # Index composite pour les requêtes de filtrage les plus courantes
            models.Index(fields=["level", "timestamp"], name="idx_level_timestamp"),
            models.Index(fields=["source", "timestamp"], name="idx_source_timestamp"),
            models.Index(fields=["timestamp"], name="idx_timestamp"),
        ]

    def __str__(self):
        return f"[{self.level}] {self.timestamp:%Y-%m-%d %H:%M:%S} — {self.message[:80]}"

    @property
    def level_color_class(self):
        """Classes CSS Tailwind selon le niveau de sévérité."""
        return {
            self.Level.DEBUG: "text-slate-400 bg-slate-800",
            self.Level.INFO: "text-blue-400 bg-blue-900/30",
            self.Level.WARNING: "text-amber-400 bg-amber-900/30",
            self.Level.ERROR: "text-red-400 bg-red-900/30",
            self.Level.CRITICAL: "text-red-300 bg-red-950 font-bold",
        }.get(self.level, "text-slate-400 bg-slate-800")

    @property
    def level_dot_class(self):
        """Couleur du point de statut (sidebar / table)."""
        return {
            self.Level.DEBUG: "bg-slate-500",
            self.Level.INFO: "bg-blue-500",
            self.Level.WARNING: "bg-amber-500",
            self.Level.ERROR: "bg-red-500",
            self.Level.CRITICAL: "bg-red-400 animate-pulse",
        }.get(self.level, "bg-slate-500")

    @property
    def has_traceback(self):
        return bool(self.traceback)
