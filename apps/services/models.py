"""
apps/services/models.py
─────────────────────────────────────────────────────────────────
Modèle Service : représente un microservice ou une application.
Suit le statut, les métriques de performance (latence, taux d'erreur)
et les dépendances entre services.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Service(models.Model):
    """
    Microservice ou application de l'infrastructure.
    Exemple : api-gateway, auth-service, worker-queue, cdn-proxy…
    """

    class Status(models.TextChoices):
        OPERATIONAL  = "operational",  _("Opérationnel")
        DEGRADED     = "degraded",     _("Dégradé")
        PARTIAL      = "partial",      _("Panne partielle")
        MAJOR        = "major",        _("Panne majeure")
        MAINTENANCE  = "maintenance",  _("Maintenance")
        UNKNOWN      = "unknown",      _("Inconnu")

    class ServiceType(models.TextChoices):
        API       = "api",       _("API REST")
        WORKER    = "worker",    _("Worker / Queue")
        DATABASE  = "database",  _("Base de données")
        CACHE     = "cache",     _("Cache")
        PROXY     = "proxy",     _("Proxy / LB")
        SCHEDULER = "scheduler", _("Planificateur")
        OTHER     = "other",     _("Autre")

    name         = models.CharField(max_length=100, unique=True, verbose_name=_("Nom"), db_index=True)
    display_name = models.CharField(max_length=100, blank=True, verbose_name=_("Nom affiché"))
    description  = models.TextField(blank=True, verbose_name=_("Description"))
    service_type = models.CharField(max_length=15, choices=ServiceType.choices,
                                    default=ServiceType.API, verbose_name=_("Type"))
    status       = models.CharField(max_length=15, choices=Status.choices,
                                    default=Status.UNKNOWN, verbose_name=_("Statut"), db_index=True)
    version      = models.CharField(max_length=50, blank=True, verbose_name=_("Version"))
    endpoint     = models.URLField(blank=True, verbose_name=_("URL / Endpoint"))

    # ── Métriques de performance ──────────────────────────────────────
    # Latence moyenne en ms (dernière valeur)
    avg_latency_ms   = models.FloatField(null=True, blank=True, verbose_name=_("Latence moy. (ms)"))
    p95_latency_ms   = models.FloatField(null=True, blank=True, verbose_name=_("Latence p95 (ms)"))
    # Taux d'erreur (%)
    error_rate       = models.FloatField(null=True, blank=True, verbose_name=_("Taux d'erreur (%)"))
    # Requêtes par seconde
    requests_per_sec = models.FloatField(null=True, blank=True, verbose_name=_("Req/s"))
    # Uptime sur 30 jours (%)
    uptime_30d       = models.FloatField(null=True, blank=True, verbose_name=_("Uptime 30j (%)"))

    # ── Timestamps ───────────────────────────────────────────────────
    last_check  = models.DateTimeField(null=True, blank=True, verbose_name=_("Dernier check"))
    is_active   = models.BooleanField(default=True, verbose_name=_("Actif"))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # ── Source de logs associée ───────────────────────────────────────
    log_source = models.OneToOneField(
        "logs.LogSource",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="service",
        verbose_name=_("Source de logs"),
    )

    class Meta:
        verbose_name = _("Service")
        verbose_name_plural = _("Services")
        ordering = ["service_type", "name"]

    def __str__(self):
        return self.display_name or self.name

    @property
    def status_color(self):
        return {
            self.Status.OPERATIONAL: "text-emerald-400 bg-emerald-950 border-emerald-800",
            self.Status.DEGRADED:    "text-amber-400 bg-amber-950 border-amber-800",
            self.Status.PARTIAL:     "text-orange-400 bg-orange-950 border-orange-800",
            self.Status.MAJOR:       "text-red-400 bg-red-950 border-red-800",
            self.Status.MAINTENANCE: "text-blue-400 bg-blue-950 border-blue-800",
            self.Status.UNKNOWN:     "text-slate-400 bg-slate-800 border-slate-700",
        }.get(self.status, "text-slate-400 bg-slate-800 border-slate-700")

    @property
    def status_dot(self):
        return {
            self.Status.OPERATIONAL: "bg-emerald-400",
            self.Status.DEGRADED:    "bg-amber-400 animate-pulse",
            self.Status.PARTIAL:     "bg-orange-400 animate-pulse",
            self.Status.MAJOR:       "bg-red-400 animate-pulse",
            self.Status.MAINTENANCE: "bg-blue-400",
            self.Status.UNKNOWN:     "bg-slate-500",
        }.get(self.status, "bg-slate-500")

    @property
    def latency_color(self):
        if not self.avg_latency_ms: return "text-[#8B949E]"
        if self.avg_latency_ms >= 1000: return "text-red-400"
        if self.avg_latency_ms >= 500:  return "text-amber-400"
        return "text-emerald-400"

    @property
    def error_rate_color(self):
        if not self.error_rate: return "text-[#8B949E]"
        if self.error_rate >= 5:  return "text-red-400"
        if self.error_rate >= 1:  return "text-amber-400"
        return "text-emerald-400"
