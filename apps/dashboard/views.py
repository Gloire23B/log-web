"""
apps/dashboard/views.py
─────────────────────────────────────────────────────────────────
Vues du dashboard principal (CBV).

DashboardView    → Vue principale avec KPIs + données de graphiques
LogVolumeAPI     → Endpoint HTMX pour le graphique de volume (JSON)
RecentLogsHtmx   → Endpoint HTMX pour rafraîchissement du tableau de logs
"""

import json
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.template.loader import render_to_string

from apps.logs.models import LogEntry, LogSource
from apps.alerts.models import Alert


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Vue principale du dashboard.
    Charge les KPIs, les statistiques par niveau,
    et les dernières entrées de logs.
    """
    template_name = "dashboard/index.html"
    login_url = "/auth/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        since_1h = now - timedelta(hours=1)

        # ── KPI Cards ─────────────────────────────────────────────────────────
        # Requête unique avec annotations pour éviter N+1
        level_counts = LogEntry.objects.filter(
            timestamp__gte=since_24h
        ).values("level").annotate(count=Count("id"))

        counts_map = {item["level"]: item["count"] for item in level_counts}

        total_24h = sum(counts_map.values())
        error_count = counts_map.get("ERROR", 0) + counts_map.get("CRITICAL", 0)
        warning_count = counts_map.get("WARNING", 0)
        info_count = counts_map.get("INFO", 0)

        # Variation par rapport à la période précédente (24h avant)
        since_48h = now - timedelta(hours=48)
        total_prev = LogEntry.objects.filter(
            timestamp__gte=since_48h,
            timestamp__lt=since_24h
        ).count()
        error_prev = LogEntry.objects.filter(
            timestamp__gte=since_48h,
            timestamp__lt=since_24h,
            level__in=["ERROR", "CRITICAL"]
        ).count()

        # ── Sources actives ──────────────────────────────────────────────────
        active_sources = LogSource.objects.filter(
            is_active=True,
            log_entries__timestamp__gte=since_24h
        ).distinct().count()

        # ── Alertes actives ──────────────────────────────────────────────────
        active_alerts = Alert.objects.filter(status="active").count()
        critical_alerts = Alert.objects.filter(
            status="active",
            severity="critical"
        ).count()

        # ── Logs récents (tableau) ───────────────────────────────────────────
        # select_related pour éviter N+1 sur source
        recent_logs = LogEntry.objects.select_related("source").filter(
            timestamp__gte=since_24h
        ).order_by("-timestamp")[:20]

        # ── Top sources par volume d'erreurs ─────────────────────────────────
        top_error_sources = (
            LogEntry.objects
            .filter(
                timestamp__gte=since_24h,
                level__in=["ERROR", "CRITICAL"]
            )
            .values("source__name")
            .annotate(error_count=Count("id"))
            .order_by("-error_count")[:5]
        )

        # ── Données graphique (24 dernières heures, par heure) ───────────────
        chart_data = self._get_hourly_chart_data(now)

        context.update({
            "page_title": "Dashboard — LogMonitor",
            # KPIs
            "total_24h": total_24h,
            "total_prev": total_prev,
            "error_count": error_count,
            "error_prev": error_prev,
            "warning_count": warning_count,
            "info_count": info_count,
            "active_sources": active_sources,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            # Tableau
            "recent_logs": recent_logs,
            # Sources
            "top_error_sources": top_error_sources,
            # Graphique (sérialisé en JSON pour Chart.js)
            "chart_data_json": json.dumps(chart_data),
            # Niveau de sévérité global
            "health_status": self._compute_health(error_count, critical_alerts),
        })
        return context

    def _get_hourly_chart_data(self, now):
        """
        Construit les données du graphique de volume horaire (24h).
        Retourne un dict prêt pour Chart.js.
        """
        since_24h = now - timedelta(hours=24)
        labels = []
        errors = []
        warnings = []
        infos = []

        for i in range(24):
            hour_start = since_24h + timedelta(hours=i)
            hour_end = hour_start + timedelta(hours=1)
            labels.append(hour_start.strftime("%H:%M"))

            # Requête par tranche horaire
            bucket = LogEntry.objects.filter(
                timestamp__gte=hour_start,
                timestamp__lt=hour_end,
            ).values("level").annotate(n=Count("id"))

            bucket_map = {r["level"]: r["n"] for r in bucket}
            errors.append(bucket_map.get("ERROR", 0) + bucket_map.get("CRITICAL", 0))
            warnings.append(bucket_map.get("WARNING", 0))
            infos.append(bucket_map.get("INFO", 0))

        return {
            "labels": labels,
            "datasets": [
                {"label": "Erreurs", "data": errors, "color": "#EF4444"},
                {"label": "Warnings", "data": warnings, "color": "#F59E0B"},
                {"label": "Info", "data": infos, "color": "#3B82F6"},
            ],
        }

    def _compute_health(self, error_count, critical_alerts):
        """
        Calcule le statut de santé global du système.
        Retourne un dict {status, label, class}.
        """
        if critical_alerts > 0 or error_count > 100:
            return {"status": "critical", "label": "Critique", "class": "text-red-400"}
        if error_count > 20:
            return {"status": "degraded", "label": "Dégradé", "class": "text-amber-400"}
        return {"status": "healthy", "label": "Opérationnel", "class": "text-emerald-400"}


class RecentLogsHtmxView(LoginRequiredMixin, View):
    """
    Endpoint HTMX pour rafraîchir le tableau des logs récents.
    Appelé via hx-get toutes les 30 secondes ou sur action utilisateur.
    Supporte les filtres : level, source_id, search.
    """
    login_url = "/auth/login/"

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        since_24h = now - timedelta(hours=24)

        qs = LogEntry.objects.select_related("source").filter(
            timestamp__gte=since_24h
        )

        # ── Filtres dynamiques ────────────────────────────────────────────────
        level = request.GET.get("level", "")
        source_id = request.GET.get("source_id", "")
        search = request.GET.get("search", "").strip()

        if level:
            qs = qs.filter(level=level)
        if source_id:
            qs = qs.filter(source_id=source_id)
        if search:
            qs = qs.filter(
                Q(message__icontains=search) |
                Q(source__name__icontains=search) |
                Q(logger_name__icontains=search)
            )

        logs = qs.order_by("-timestamp")[:50]

        html = render_to_string(
            "partials/log_table_rows.html",
            {"recent_logs": logs},
            request=request,
        )
        return HttpResponse(html)


class LogVolumeChartView(LoginRequiredMixin, View):
    """
    Endpoint HTMX/JSON pour le graphique de volume.
    Permet de changer la période (1h, 6h, 24h, 7d) sans rechargement.
    """
    login_url = "/auth/login/"

    def get(self, request, *args, **kwargs):
        period = request.GET.get("period", "24h")
        now = timezone.now()

        # Paramètres selon la période choisie
        period_config = {
            "1h": (timedelta(hours=1), timedelta(minutes=5), "%H:%M"),
            "6h": (timedelta(hours=6), timedelta(minutes=30), "%H:%M"),
            "24h": (timedelta(hours=24), timedelta(hours=1), "%H:%M"),
            "7d": (timedelta(days=7), timedelta(hours=6), "%d/%m %H:%M"),
        }
        delta, bucket_size, fmt = period_config.get(period, period_config["24h"])
        since = now - delta
        buckets = int(delta / bucket_size)

        labels, errors, warnings, infos = [], [], [], []
        for i in range(buckets):
            start = since + bucket_size * i
            end = start + bucket_size
            labels.append(start.strftime(fmt))
            bucket = LogEntry.objects.filter(
                timestamp__gte=start, timestamp__lt=end
            ).values("level").annotate(n=Count("id"))
            bmap = {r["level"]: r["n"] for r in bucket}
            errors.append(bmap.get("ERROR", 0) + bmap.get("CRITICAL", 0))
            warnings.append(bmap.get("WARNING", 0))
            infos.append(bmap.get("INFO", 0))

        return JsonResponse({
            "labels": labels,
            "datasets": [
                {"label": "Erreurs", "data": errors, "color": "#EF4444"},
                {"label": "Warnings", "data": warnings, "color": "#F59E0B"},
                {"label": "Info", "data": infos, "color": "#3B82F6"},
            ],
        })
