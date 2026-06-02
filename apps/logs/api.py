"""
apps/logs/api.py
─────────────────────────────────────────────────────────────────
API REST légère pour l'ingestion de logs.
Aucune dépendance DRF — implémentée avec des vues Django natives
pour rester dans la stack technique du projet.

Endpoints :
  POST /api/v1/logs/ingest/       → Ingestion simple (1 log)
  POST /api/v1/logs/ingest/bulk/  → Ingestion en batch (N logs)
  GET  /api/v1/health/            → Health check de l'API

Authentification : Token dans l'en-tête X-API-Key
Format : application/json

Exemple d'appel :
  curl -X POST http://localhost:8000/api/v1/logs/ingest/ \\
       -H "Content-Type: application/json" \\
       -H "X-API-Key: votre-token" \\
       -d '{"level":"ERROR","message":"Disk full","source":"web-01"}'
"""

import json
import logging
from functools import wraps

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings

from .models import LogEntry, LogSource

logger = logging.getLogger("apps.logs.api")


# ══════════════════════════════════════════════════════════════════════════════
# Authentification par API Key
# ══════════════════════════════════════════════════════════════════════════════

def require_api_key(view_func):
    """
    Décorateur d'authentification par clé API.
    La clé est lue depuis le header X-API-Key.
    Configurée dans settings.py via API_KEYS (liste de clés valides).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = request.META.get("HTTP_X_API_KEY", "")
        valid_keys = getattr(settings, "API_KEYS", [])

        # En développement, accepter toutes les requêtes si pas de clé configurée
        if not valid_keys and settings.DEBUG:
            return view_func(request, *args, **kwargs)

        if not api_key or api_key not in valid_keys:
            logger.warning(f"API: Tentative d'accès non autorisée depuis {request.META.get('REMOTE_ADDR')}")
            return JsonResponse(
                {"error": "Clé API manquante ou invalide", "code": "unauthorized"},
                status=401
            )
        return view_func(request, *args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de validation
# ══════════════════════════════════════════════════════════════════════════════

VALID_LEVELS = {choice[0] for choice in LogEntry.Level.choices}

def validate_log_payload(data: dict) -> tuple[dict | None, str | None]:
    """
    Valide et normalise un payload de log.
    Retourne (log_dict, None) si valide, (None, message_erreur) sinon.
    """
    # Champs obligatoires
    message = data.get("message", "").strip()
    if not message:
        return None, "Le champ 'message' est obligatoire et ne peut être vide."

    # Niveau — normalisation en majuscules
    level = str(data.get("level", "INFO")).upper()
    if level not in VALID_LEVELS:
        return None, f"Niveau invalide '{level}'. Valeurs acceptées : {', '.join(VALID_LEVELS)}"

    # Timestamp — optionnel, défaut = maintenant
    timestamp_raw = data.get("timestamp")
    if timestamp_raw:
        try:
            from django.utils.dateparse import parse_datetime
            timestamp = parse_datetime(str(timestamp_raw))
            if not timestamp:
                raise ValueError("Format non reconnu")
            if not timestamp.tzinfo:
                timestamp = timezone.make_aware(timestamp)
        except (ValueError, TypeError):
            return None, f"Format de timestamp invalide : '{timestamp_raw}'. Utilisez ISO 8601."
    else:
        timestamp = timezone.now()

    return {
        "level": level,
        "message": message[:10000],   # Limiter la taille du message
        "timestamp": timestamp,
        "source_name": data.get("source", ""),
        "logger_name": str(data.get("logger", ""))[:200],
        "traceback": str(data.get("traceback", ""))[:50000],
        "extra_data": data.get("extra", {}) if isinstance(data.get("extra"), dict) else {},
        "file_path": str(data.get("file", ""))[:500],
        "line_number": int(data["line"]) if str(data.get("line", "")).isdigit() else None,
    }, None


def _get_or_create_source(source_name: str) -> LogSource | None:
    """
    Retourne la source existante ou en crée une nouvelle automatiquement.
    Utilise get_or_create pour être thread-safe.
    """
    if not source_name:
        return None
    source, created = LogSource.objects.get_or_create(
        name=source_name[:100],
        defaults={"source_type": LogSource.SourceType.APPLICATION}
    )
    if created:
        logger.info(f"API: Nouvelle source créée automatiquement : {source_name}")
    return source


def _build_log_entry(validated: dict) -> LogEntry:
    """Construit un LogEntry à partir des données validées (sans sauvegarder)."""
    source = _get_or_create_source(validated["source_name"])
    return LogEntry(
        level=validated["level"],
        message=validated["message"],
        timestamp=validated["timestamp"],
        source=source,
        logger_name=validated["logger_name"],
        traceback=validated["traceback"],
        extra_data=validated["extra_data"],
        file_path=validated["file_path"],
        line_number=validated["line_number"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Vues API
# ══════════════════════════════════════════════════════════════════════════════

@method_decorator([csrf_exempt, require_api_key], name="dispatch")
class LogIngestView(View):
    """
    POST /api/v1/logs/ingest/
    Ingestion d'un seul log.

    Body JSON :
    {
        "level":   "ERROR",               # obligatoire
        "message": "Connection refused",   # obligatoire
        "source":  "api-gateway",          # optionnel
        "timestamp": "2025-01-15T14:22:05Z", # optionnel, défaut = now
        "logger":  "django.request",       # optionnel
        "traceback": "...",                # optionnel
        "extra":   {"user_id": 42},        # optionnel, JSON
        "file":    "apps/views.py",        # optionnel
        "line":    "127"                   # optionnel
    }

    Réponses :
      201 → Log ingéré avec succès
      400 → Payload invalide
      401 → Clé API manquante/invalide
      405 → Méthode non autorisée
    """

    def post(self, request, *args, **kwargs):
        # ── Parsing JSON ──────────────────────────────────────────────
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return JsonResponse(
                {"error": f"JSON invalide : {e}", "code": "invalid_json"},
                status=400
            )

        if not isinstance(data, dict):
            return JsonResponse(
                {"error": "Le payload doit être un objet JSON", "code": "invalid_format"},
                status=400
            )

        # ── Validation ────────────────────────────────────────────────
        validated, error = validate_log_payload(data)
        if error:
            return JsonResponse({"error": error, "code": "validation_error"}, status=400)

        # ── Création du log ───────────────────────────────────────────
        log_entry = _build_log_entry(validated)
        log_entry.save()

        # ── Notifications asynchrones ─────────────────────────────────
        # Déclenchement non-bloquant : les erreurs sont loggées silencieusement
        try:
            from .notifications import NotificationService
            NotificationService.notify_log(log_entry)
        except Exception:
            pass  # Ne jamais bloquer l'ingestion à cause des notifications

        logger.debug(f"API: Log ingéré #{log_entry.pk} [{log_entry.level}] {log_entry.message[:80]}")

        return JsonResponse({
            "id": log_entry.pk,
            "level": log_entry.level,
            "timestamp": log_entry.timestamp.isoformat(),
            "message": "Log ingéré avec succès",
        }, status=201)


@method_decorator([csrf_exempt, require_api_key], name="dispatch")
class LogIngestBulkView(View):
    """
    POST /api/v1/logs/ingest/bulk/
    Ingestion par batch pour un volume important de logs.
    Limite : 1000 logs par requête.

    Body JSON :
    {
        "logs": [
            {"level": "INFO", "message": "...", "source": "..."},
            {"level": "ERROR", "message": "...", ...},
            ...
        ]
    }

    Réponses :
      201 → {"ingested": N, "errors": [...]}
      400 → Payload invalide
    """
    MAX_BATCH_SIZE = 1000

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return JsonResponse({"error": f"JSON invalide : {e}", "code": "invalid_json"}, status=400)

        logs_data = data.get("logs")
        if not isinstance(logs_data, list):
            return JsonResponse(
                {"error": "Le champ 'logs' doit être une liste", "code": "invalid_format"},
                status=400
            )

        if len(logs_data) == 0:
            return JsonResponse({"error": "La liste 'logs' est vide", "code": "empty_batch"}, status=400)

        if len(logs_data) > self.MAX_BATCH_SIZE:
            return JsonResponse(
                {"error": f"Trop de logs dans le batch (max {self.MAX_BATCH_SIZE})", "code": "batch_too_large"},
                status=400
            )

        # ── Validation de chaque log ──────────────────────────────────
        valid_entries = []
        errors = []

        for idx, log_data in enumerate(logs_data):
            if not isinstance(log_data, dict):
                errors.append({"index": idx, "error": "Entrée invalide (objet JSON attendu)"})
                continue

            validated, error = validate_log_payload(log_data)
            if error:
                errors.append({"index": idx, "error": error})
                continue

            valid_entries.append(_build_log_entry(validated))

        # ── Insertion batch ───────────────────────────────────────────
        if valid_entries:
            LogEntry.objects.bulk_create(valid_entries, batch_size=200)
            logger.info(f"API Bulk: {len(valid_entries)} logs ingérés, {len(errors)} erreurs")

        return JsonResponse({
            "ingested": len(valid_entries),
            "errors": errors,
            "total": len(logs_data),
        }, status=201)


@method_decorator([csrf_exempt, require_api_key], name="dispatch")
class ServerMetricsIngestView(View):
    """
    POST /api/v1/servers/metrics/
    Mise à jour des métriques d'un serveur depuis un agent distant.

    Body JSON :
    {
        "server_name": "web-prod-01",    # obligatoire — nom exact dans LogMonitor
        "cpu_percent":    45.2,          # optionnel
        "memory_percent": 67.8,          # optionnel
        "disk_percent":   23.1,          # optionnel
        "load_average":   1.2,           # optionnel
        "uptime_seconds": 86400          # optionnel
    }

    Réponses :
      200 → Métriques mises à jour
      400 → Payload invalide
      404 → Serveur introuvable
    """

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return JsonResponse({"error": f"JSON invalide : {e}"}, status=400)

        server_name = (data.get("server_name") or "").strip()
        if not server_name:
            return JsonResponse({"error": "Le champ 'server_name' est obligatoire."}, status=400)

        from apps.servers.models import Server
        try:
            server = Server.objects.get(name=server_name)
        except Server.DoesNotExist:
            # Tentative insensible à la casse
            try:
                server = Server.objects.get(name__iexact=server_name)
            except Server.DoesNotExist:
                return JsonResponse(
                    {"error": f"Serveur introuvable : '{server_name}'"},
                    status=404
                )

        update_fields = ["last_seen", "status"]
        server.last_seen = timezone.now()

        for field in ["cpu_percent", "memory_percent", "disk_percent", "load_average", "uptime_seconds"]:
            value = data.get(field)
            if value is not None:
                try:
                    setattr(server, field, float(value))
                    update_fields.append(field)
                except (TypeError, ValueError):
                    pass

        server.compute_status()
        server.save(update_fields=list(set(update_fields)))

        logger.info(
            f"API Metrics: serveur '{server.name}' mis à jour — "
            f"CPU={server.cpu_percent}% RAM={server.memory_percent}% Disk={server.disk_percent}%"
        )

        return JsonResponse({
            "server": server.name,
            "status": server.status,
            "last_seen": server.last_seen.isoformat(),
            "message": "Métriques mises à jour avec succès.",
        }, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class HealthCheckView(View):
    """
    GET /api/v1/health/
    Health check de l'API — accessible sans authentification.
    Vérifie la connexion à la base de données.
    """

    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_ok = True
        except Exception:
            db_ok = False

        status_code = 200 if db_ok else 503
        return JsonResponse({
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "error",
            "timestamp": timezone.now().isoformat(),
            "version": "2.1.0",
        }, status=status_code)
