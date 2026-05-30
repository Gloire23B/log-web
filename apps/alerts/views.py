"""
apps/alerts/views.py
─────────────────────────────────────────────────────────────────
Vues du système d'alertes (CBV).

AlertListView        → Liste paginée avec filtres sévérité/statut
AlertAcknowledgeView → Acquittement via POST HTMX (pas de rechargement)
AlertResolveView     → Résolution via POST HTMX
AlertStatsHtmxView  → Compteurs live pour la sidebar (polling)
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.template.loader import render_to_string

from .models import Alert


class AlertListView(LoginRequiredMixin, ListView):
    """
    Liste des alertes avec filtres dynamiques HTMX.
    Trie par défaut : actives en premier, puis par date décroissante.
    """
    model = Alert
    template_name = "alerts/list.html"
    context_object_name = "alerts"
    login_url = "/auth/login/"
    paginate_by = 25

    def get_queryset(self):
        qs = Alert.objects.select_related("source", "acknowledged_by", "trigger_log")

        severity = self.request.GET.get("severity", "")
        status   = self.request.GET.get("status", "active")  # actives par défaut
        search   = self.request.GET.get("search", "").strip()

        if severity:
            qs = qs.filter(severity=severity)
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(source__name__icontains=search)
            )

        # Actives d'abord, puis par date
        return qs.order_by(
            # Ordre personnalisé : active → acknowledged → resolved
            "status",
            "-triggered_at",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Compteurs par sévérité (pour les badges)
        counts = Alert.objects.filter(status="active").values("severity").annotate(n=Count("id"))
        severity_counts = {r["severity"]: r["n"] for r in counts}

        context.update({
            "page_title": "Alertes — LogMonitor",
            "severity_choices": Alert.Severity.choices,
            "status_choices": Alert.Status.choices,
            "filters": {
                "severity": self.request.GET.get("severity", ""),
                "status": self.request.GET.get("status", "active"),
                "search": self.request.GET.get("search", ""),
            },
            "severity_counts": severity_counts,
            "total_active": sum(severity_counts.values()),
            "critical_count": severity_counts.get("critical", 0),
        })
        return context


class AlertAcknowledgeView(LoginRequiredMixin, View):
    """
    Acquittement d'une alerte via POST (HTMX).
    Retourne la ligne mise à jour sans rechargement de page.
    """
    login_url = "/auth/login/"

    def post(self, request, pk, *args, **kwargs):
        alert = get_object_or_404(Alert, pk=pk)

        if alert.status == Alert.Status.ACTIVE:
            alert.status = Alert.Status.ACKNOWLEDGED
            alert.acknowledged_by = request.user
            alert.acknowledged_at = timezone.now()
            alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])

        # Retourne la ligne HTML mise à jour via HTMX
        html = render_to_string(
            "partials/alert_row.html",
            {"alert": alert},
            request=request,
        )
        return HttpResponse(html)


class AlertResolveView(LoginRequiredMixin, View):
    """
    Résolution d'une alerte via POST (HTMX).
    """
    login_url = "/auth/login/"

    def post(self, request, pk, *args, **kwargs):
        alert = get_object_or_404(Alert, pk=pk)

        if alert.status != Alert.Status.RESOLVED:
            alert.status = Alert.Status.RESOLVED
            alert.resolved_at = timezone.now()
            if not alert.acknowledged_by:
                alert.acknowledged_by = request.user
                alert.acknowledged_at = timezone.now()
            alert.save(update_fields=[
                "status", "resolved_at", "acknowledged_by", "acknowledged_at"
            ])

        html = render_to_string(
            "partials/alert_row.html",
            {"alert": alert},
            request=request,
        )
        return HttpResponse(html)


class AlertStatsHtmxView(LoginRequiredMixin, View):
    """
    Endpoint HTMX pour le compteur live d'alertes (polling 60s).
    Retourne uniquement les badges de compteurs.
    """
    login_url = "/auth/login/"

    def get(self, request, *args, **kwargs):
        counts = Alert.objects.filter(status="active").aggregate(
            total=Count("id"),
            critical=Count("id", filter=Q(severity="critical")),
            high=Count("id", filter=Q(severity="high")),
        )
        html = render_to_string(
            "partials/alert_stats_badge.html",
            counts,
            request=request,
        )
        return HttpResponse(html)
