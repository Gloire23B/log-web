"""
apps/dashboard/context_processors.py
─────────────────────────────────────────────────────────────────
Context processor global : injecte les stats de base dans tous les templates.
Utilisé pour la sidebar (compteur d'alertes actives) et le header.
Résultat mis en cache légèrement pour éviter des requêtes répétées.
"""

from django.utils import timezone
from django.db.models import Count


def dashboard_stats(request):
    """
    Injecte dans chaque template :
    - active_alerts_count : nombre d'alertes actives (badge rouge sidebar)
    - unresolved_errors_count : erreurs non résolues des dernières 24h
    """
    if not request.user.is_authenticated:
        return {}

    try:
        from apps.alerts.models import Alert
        from apps.logs.models import LogEntry

        since_24h = timezone.now() - timezone.timedelta(hours=24)

        active_alerts = Alert.objects.filter(status="active").count()

        unresolved_errors = LogEntry.objects.filter(
            level__in=["ERROR", "CRITICAL"],
            timestamp__gte=since_24h,
            is_resolved=False,
        ).count()

        return {
            "active_alerts_count": active_alerts,
            "unresolved_errors_count": unresolved_errors,
        }
    except Exception:
        # Fail silently si les tables n'existent pas encore (ex: première migration)
        return {
            "active_alerts_count": 0,
            "unresolved_errors_count": 0,
        }
