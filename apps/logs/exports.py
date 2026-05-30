"""
apps/logs/exports.py
─────────────────────────────────────────────────────────────────
Export de logs en CSV et JSON.
Utilise StreamingHttpResponse pour les gros volumes
afin d'éviter de charger toute la queryset en mémoire.

Endpoints :
  GET /logs/export/csv/    → Téléchargement CSV (jusqu'à 10 000 lignes)
  GET /logs/export/json/   → Téléchargement JSON (jusqu'à 10 000 lignes)
"""

import csv
import json
import io
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import StreamingHttpResponse, HttpResponse
from django.views import View
from django.db.models import Q
from django.utils import timezone

from .models import LogEntry


# ── Limite de sécurité pour l'export ─────────────────────────────────────────
EXPORT_LIMIT = 10_000


def _apply_filters(request) -> "QuerySet":
    """
    Applique les mêmes filtres que LogListView sur la queryset d'export.
    Centralise la logique de filtrage pour éviter la duplication.
    """
    qs = LogEntry.objects.select_related("source").all()

    level     = request.GET.get("level", "")
    source_id = request.GET.get("source_id", "")
    search    = request.GET.get("search", "").strip()
    date_from = request.GET.get("date_from", "")
    date_to   = request.GET.get("date_to", "")

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
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)

    return qs.order_by("-timestamp")[:EXPORT_LIMIT]


class LogExportCSVView(LoginRequiredMixin, View):
    """
    Export CSV des logs avec StreamingHttpResponse.
    Streaming : les lignes sont envoyées au client au fur et à mesure
    sans charger toute la queryset en RAM.
    """
    login_url = "/auth/login/"

    def get(self, request, *args, **kwargs):
        queryset = _apply_filters(request)
        filename = f"logs_export_{datetime.now():%Y%m%d_%H%M%S}.csv"

        response = StreamingHttpResponse(
            self._stream_csv(queryset),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Export-Count"] = str(EXPORT_LIMIT)
        return response

    def _stream_csv(self, queryset):
        """Générateur : yield les lignes CSV une par une."""
        # En-têtes
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "ID", "Timestamp", "Niveau", "Source",
            "Logger", "Message", "Traceback", "Résolu",
            "Fichier", "Ligne", "Ingéré le"
        ])
        yield buffer.getvalue()

        # Lignes de données
        for log in queryset.iterator(chunk_size=500):
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow([
                log.pk,
                log.timestamp.isoformat(),
                log.level,
                log.source.name if log.source else "",
                log.logger_name,
                log.message,
                log.traceback,
                "Oui" if log.is_resolved else "Non",
                log.file_path,
                log.line_number or "",
                log.ingested_at.isoformat(),
            ])
            yield buffer.getvalue()


class LogExportJSONView(LoginRequiredMixin, View):
    """
    Export JSON des logs.
    Retourne un fichier JSON structuré avec métadonnées d'export.
    """
    login_url = "/auth/login/"

    def get(self, request, *args, **kwargs):
        queryset = _apply_filters(request)
        filename = f"logs_export_{datetime.now():%Y%m%d_%H%M%S}.json"

        logs_data = []
        for log in queryset:
            logs_data.append({
                "id":          log.pk,
                "timestamp":   log.timestamp.isoformat(),
                "level":       log.level,
                "source":      log.source.name if log.source else None,
                "logger":      log.logger_name or None,
                "message":     log.message,
                "traceback":   log.traceback or None,
                "extra":       log.extra_data if log.extra_data else None,
                "file":        log.file_path or None,
                "line":        log.line_number,
                "is_resolved": log.is_resolved,
                "ingested_at": log.ingested_at.isoformat(),
            })

        payload = {
            "export_meta": {
                "exported_at":  timezone.now().isoformat(),
                "exported_by":  request.user.username,
                "total_count":  len(logs_data),
                "max_records":  EXPORT_LIMIT,
                "filters": {
                    "level":     request.GET.get("level") or None,
                    "source_id": request.GET.get("source_id") or None,
                    "search":    request.GET.get("search") or None,
                    "date_from": request.GET.get("date_from") or None,
                    "date_to":   request.GET.get("date_to") or None,
                },
            },
            "logs": logs_data,
        }

        response = HttpResponse(
            json.dumps(payload, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
