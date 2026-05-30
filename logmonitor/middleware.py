"""
logmonitor/middleware.py
─────────────────────────────────────────────────────────────────
Middleware de rate limiting pour l'API REST d'ingestion.

Algorithme : compteur glissant par fenêtre (sliding window).
Stockage   : mémoire (dict thread-safe) en dev,
             cache Django (Redis) en production.

Limites par défaut :
  - 1 000 requêtes / minute par IP
  - 10 000 requêtes / minute par clé API

Configuration dans settings.py :
    API_RATE_LIMIT_PER_IP  = 1000   # req/min
    API_RATE_LIMIT_PER_KEY = 10000  # req/min
    API_RATE_LIMIT_WINDOW  = 60     # secondes
"""

import time
import logging
import threading
from collections import defaultdict, deque

from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger("apps.logs.ratelimit")


# ══════════════════════════════════════════════════════════════════════════════
# Store en mémoire (développement)
# ══════════════════════════════════════════════════════════════════════════════

class InMemoryRateLimitStore:
    """
    Store de rate limiting en mémoire avec sliding window.
    Thread-safe via verrou. Nettoyage automatique des entrées expirées.
    ⚠ Non partagé entre workers Gunicorn — utiliser Redis en production.
    """

    def __init__(self):
        self._store: dict[str, deque] = defaultdict(deque)
        self._lock  = threading.Lock()
        self._last_cleanup = time.time()

    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Vérifie si la requête est autorisée.
        Retourne (autorisé, nombre_restant).
        """
        now = time.time()
        cutoff = now - window

        with self._lock:
            timestamps = self._store[key]

            # Supprime les timestamps hors fenêtre
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            count = len(timestamps)

            if count >= limit:
                remaining = 0
                # Nettoyage périodique (toutes les 5 minutes)
                if now - self._last_cleanup > 300:
                    self._cleanup(cutoff)
                return False, remaining

            timestamps.append(now)
            remaining = limit - count - 1
            return True, remaining

    def _cleanup(self, cutoff: float) -> None:
        """Supprime les clés expirées pour libérer la mémoire."""
        expired = [k for k, v in self._store.items() if not v or v[-1] < cutoff]
        for k in expired:
            del self._store[k]
        self._last_cleanup = time.time()
        logger.debug(f"Rate limit cleanup: {len(expired)} clés supprimées")


# Instance singleton
_memory_store = InMemoryRateLimitStore()


def _get_client_ip(request) -> str:
    """Récupère l'IP réelle du client (derrière proxy/load balancer)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


# ══════════════════════════════════════════════════════════════════════════════
# Middleware
# ══════════════════════════════════════════════════════════════════════════════

class ApiRateLimitMiddleware:
    """
    Middleware de rate limiting appliqué uniquement aux routes /api/.
    Les routes dashboard/logs/admin ne sont pas affectées.

    Headers de réponse injectés :
      X-RateLimit-Limit     : limite configurée
      X-RateLimit-Remaining : requêtes restantes
      X-RateLimit-Reset     : timestamp Unix de réinitialisation
    """

    LIMIT_PER_IP  = None  # Chargé depuis settings
    LIMIT_PER_KEY = None
    WINDOW        = None

    def __init__(self, get_response):
        self.get_response = get_response
        # Chargement des paramètres depuis settings
        self.LIMIT_PER_IP  = getattr(settings, "API_RATE_LIMIT_PER_IP",  1000)
        self.LIMIT_PER_KEY = getattr(settings, "API_RATE_LIMIT_PER_KEY", 10000)
        self.WINDOW        = getattr(settings, "API_RATE_LIMIT_WINDOW",  60)

    def __call__(self, request):
        # Applique seulement aux routes /api/
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Health check exempt du rate limiting
        if request.path.endswith("/health/"):
            return self.get_response(request)

        api_key   = request.META.get("HTTP_X_API_KEY", "")
        client_ip = _get_client_ip(request)

        # ── Rate limit par clé API (prioritaire si présente) ─────────
        if api_key:
            key   = f"api_key:{api_key[:16]}"
            limit = self.LIMIT_PER_KEY
        else:
            key   = f"ip:{client_ip}"
            limit = self.LIMIT_PER_IP

        allowed, remaining = _memory_store.is_allowed(key, limit, self.WINDOW)

        # Headers standard de rate limiting
        reset_ts = int(time.time()) + self.WINDOW

        if not allowed:
            logger.warning(
                f"Rate limit dépassé — key={key} path={request.path}"
            )
            response = JsonResponse(
                {
                    "error": "Trop de requêtes. Réessayez dans un moment.",
                    "code":  "rate_limit_exceeded",
                    "retry_after": self.WINDOW,
                },
                status=429,
            )
            response["Retry-After"]           = str(self.WINDOW)
            response["X-RateLimit-Limit"]     = str(limit)
            response["X-RateLimit-Remaining"] = "0"
            response["X-RateLimit-Reset"]     = str(reset_ts)
            return response

        response = self.get_response(request)
        response["X-RateLimit-Limit"]     = str(limit)
        response["X-RateLimit-Remaining"] = str(remaining)
        response["X-RateLimit-Reset"]     = str(reset_ts)
        return response
