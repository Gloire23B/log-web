"""
apps/dashboard/sse.py
─────────────────────────────────────────────────────────────────
Server-Sent Events (SSE) pour les mises à jour temps réel.

Endpoint : GET /dashboard/stream/
Événements émis :
  - stats      : KPIs toutes les 10s
  - new_log    : dernier log ingéré
  - alert      : nouvelle alerte active

Le client JavaScript écoute avec EventSource() — natif dans tous
les navigateurs modernes, pas besoin de WebSocket.
Fallback : HTMX polling (déjà en place).

⚠ Requiert un serveur asynchrone (Gunicorn + eventlet/gevent)
  ou Daphne en production. En dev, Django runserver suffit.
"""

import json
import time
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import StreamingHttpResponse
from django.views import View
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta

logger = logging.getLogger("apps.dashboard.sse")


def _build_stats_payload() -> dict:
    """
    Construit le payload des KPIs pour l'événement SSE 'stats'.
    Même logique que DashboardView.get_context_data() mais allégée.
    """
    from apps.logs.models import LogEntry
    from apps.alerts.models import Alert

    now      = timezone.now()
    since_1h = now - timedelta(hours=1)

    counts = LogEntry.objects.filter(
        timestamp__gte=since_1h
    ).values("level").annotate(n=Count("id"))
    cmap = {r["level"]: r["n"] for r in counts}

    errors  = cmap.get("ERROR", 0) + cmap.get("CRITICAL", 0)
    total   = sum(cmap.values())
    alerts  = Alert.objects.filter(status="active").count()

    return {
        "total_1h":      total,
        "errors_1h":     errors,
        "warnings_1h":   cmap.get("WARNING", 0),
        "active_alerts": alerts,
        "timestamp":     now.isoformat(),
    }


def _build_latest_log_payload() -> dict | None:
    """Retourne le log le plus récent (dernière minute)."""
    from apps.logs.models import LogEntry

    log = (
        LogEntry.objects
        .select_related("source")
        .filter(timestamp__gte=timezone.now() - timedelta(minutes=1))
        .order_by("-timestamp")
        .first()
    )
    if not log:
        return None

    return {
        "id":        log.pk,
        "level":     log.level,
        "message":   log.message[:120],
        "source":    log.source.name if log.source else None,
        "timestamp": log.timestamp.isoformat(),
    }


def _sse_format(event: str, data: dict) -> str:
    """Formate un message SSE (RFC 8895)."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


class DashboardSSEView(LoginRequiredMixin, View):
    """
    Flux SSE pour le dashboard en temps réel.

    Le client se connecte une fois et reçoit des mises à jour en continu.
    Chaque cycle :
      1. Émet les stats globales (KPIs)
      2. Émet le dernier log si disponible
      3. Dort HEARTBEAT_INTERVAL secondes
      4. Recommence

    Heartbeat (commentaire SSE ':') envoyé toutes les 15s pour garder
    la connexion ouverte à travers les proxies et load balancers.
    """

    HEARTBEAT_INTERVAL = 10   # secondes entre chaque cycle
    MAX_DURATION       = 300  # durée max de connexion (5 min) → client reconnecte
    login_url = "/auth/login/"

    def get(self, request, *args, **kwargs):
        response = StreamingHttpResponse(
            self._event_stream(request),
            content_type="text/event-stream",
        )
        response["Cache-Control"]     = "no-cache"
        response["X-Accel-Buffering"] = "no"  # Désactive le buffering Nginx
        return response

    def _event_stream(self, request):
        """
        Générateur de flux SSE.
        Yield les événements formatés jusqu'à MAX_DURATION secondes.
        """
        start_time = time.time()
        last_log_id = None

        # Message de connexion initial
        yield _sse_format("connected", {"message": "Flux temps réel connecté"})

        try:
            while time.time() - start_time < self.MAX_DURATION:
                # ── Stats globales ─────────────────────────────────────
                try:
                    stats = _build_stats_payload()
                    yield _sse_format("stats", stats)
                except Exception as exc:
                    logger.error(f"SSE stats error: {exc}")

                # ── Dernier log (si nouveau) ───────────────────────────
                try:
                    latest = _build_latest_log_payload()
                    if latest and latest.get("id") != last_log_id:
                        last_log_id = latest["id"]
                        yield _sse_format("new_log", latest)
                except Exception as exc:
                    logger.error(f"SSE log error: {exc}")

                # ── Heartbeat ──────────────────────────────────────────
                yield ": heartbeat\n\n"

                time.sleep(self.HEARTBEAT_INTERVAL)

        except GeneratorExit:
            # Client déconnecté proprement
            logger.debug("SSE: Client déconnecté")
        except Exception as exc:
            logger.error(f"SSE stream error: {exc}")
            yield _sse_format("error", {"message": "Erreur du flux, reconnexion…"})
