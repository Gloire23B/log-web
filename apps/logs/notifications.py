"""
apps/logs/notifications.py
─────────────────────────────────────────────────────────────────
Système de notifications : email et webhook HTTP.

Déclenchement automatique :
  - Log CRITICAL ou ERROR → email aux admins/analysts notifyOn
  - Alerte créée          → webhook configuré

Architecture :
  NotificationService  → façade principale
  EmailNotifier        → envoi email Django
  WebhookNotifier      → POST HTTP vers URL externe (Slack, Teams, PagerDuty…)

Usage :
  from apps.logs.notifications import NotificationService
  NotificationService.notify_log(log_entry)
  NotificationService.notify_alert(alert)
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger("apps.logs.notifications")


# ══════════════════════════════════════════════════════════════════════════════
# Email Notifier
# ══════════════════════════════════════════════════════════════════════════════

class EmailNotifier:
    """Envoie des notifications email via Django's mail backend."""

    @staticmethod
    def get_recipients_for_log(log_entry) -> list[str]:
        """
        Détermine les destinataires selon la préférence de l'utilisateur
        et le niveau de sévérité du log.
        Utilise select_related pour éviter N+1.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        qs = User.objects.filter(is_active=True)

        if log_entry.level in ("CRITICAL", "ERROR"):
            qs = qs.filter(notify_on_error=True)
        elif log_entry.level == "WARNING":
            qs = qs.filter(notify_on_warning=True)
        else:
            return []

        return list(qs.values_list("email", flat=True).exclude(email=""))

    @staticmethod
    def send_log_alert(log_entry, recipients: list[str]) -> bool:
        """
        Envoie un email d'alerte pour un log critique.
        Retourne True si l'envoi a réussi.
        """
        if not recipients:
            return False

        level_emoji = {
            "CRITICAL": "🔴",
            "ERROR":    "🟠",
            "WARNING":  "🟡",
        }.get(log_entry.level, "🔵")

        subject = (
            f"{level_emoji} [{log_entry.level}] LogMonitor — "
            f"{log_entry.message[:80]}{'…' if len(log_entry.message) > 80 else ''}"
        )

        # Message texte brut
        text_body = (
            f"LogMonitor — Alerte {log_entry.level}\n"
            f"{'=' * 50}\n\n"
            f"Niveau    : {log_entry.level}\n"
            f"Horodatage: {log_entry.timestamp:%Y-%m-%d %H:%M:%S UTC}\n"
            f"Source    : {log_entry.source.name if log_entry.source else 'N/A'}\n"
            f"Logger    : {log_entry.logger_name or 'N/A'}\n\n"
            f"Message   :\n{log_entry.message}\n\n"
        )

        if log_entry.traceback:
            text_body += f"Traceback :\n{log_entry.traceback}\n\n"

        text_body += (
            f"{'=' * 50}\n"
            f"LogMonitor Dashboard — {timezone.now().year}"
        )

        try:
            send_mail(
                subject=subject,
                message=text_body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logmonitor.io"),
                recipient_list=recipients,
                fail_silently=False,
            )
            logger.info(
                f"Email envoyé pour log #{log_entry.pk} [{log_entry.level}] "
                f"à {len(recipients)} destinataire(s)"
            )
            return True
        except Exception as exc:
            logger.error(f"Erreur envoi email pour log #{log_entry.pk}: {exc}")
            return False

    @staticmethod
    def send_alert_notification(alert, recipients: list[str]) -> bool:
        """Envoie une notification email pour une nouvelle alerte."""
        if not recipients:
            return False

        subject = f"🚨 Alerte {alert.get_severity_display().upper()} — {alert.title}"
        body = (
            f"LogMonitor — Nouvelle Alerte\n"
            f"{'=' * 50}\n\n"
            f"Titre     : {alert.title}\n"
            f"Sévérité  : {alert.get_severity_display()}\n"
            f"Source    : {alert.source.name if alert.source else 'N/A'}\n"
            f"Déclenchée: {alert.triggered_at:%Y-%m-%d %H:%M:%S UTC}\n\n"
        )
        if alert.description:
            body += f"Description:\n{alert.description}\n\n"

        body += "Connectez-vous à LogMonitor pour gérer cette alerte."

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logmonitor.io"),
                recipient_list=recipients,
                fail_silently=False,
            )
            return True
        except Exception as exc:
            logger.error(f"Erreur envoi email pour alerte #{alert.pk}: {exc}")
            return False


# ══════════════════════════════════════════════════════════════════════════════
# Webhook Notifier
# ══════════════════════════════════════════════════════════════════════════════

class WebhookNotifier:
    """
    Envoie des notifications vers une URL externe via HTTP POST.
    Compatible Slack, Discord, Microsoft Teams, PagerDuty, etc.
    """

    TIMEOUT = 5  # secondes

    @classmethod
    def send(cls, url: str, payload: dict, secret: Optional[str] = None) -> bool:
        """
        Envoie le payload JSON vers l'URL de webhook.
        Signature HMAC optionnelle via le header X-LogMonitor-Signature.
        """
        if not url:
            return False

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LogMonitor/2.1",
        }

        # Signature HMAC optionnelle
        if secret:
            import hmac
            import hashlib
            sig = hmac.new(
                secret.encode(), body, hashlib.sha256
            ).hexdigest()
            headers["X-LogMonitor-Signature"] = f"sha256={sig}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=cls.TIMEOUT) as resp:
                logger.info(f"Webhook envoyé vers {url} — HTTP {resp.status}")
                return resp.status < 400
        except urllib.error.HTTPError as e:
            logger.warning(f"Webhook HTTP {e.code} vers {url}: {e.reason}")
            return False
        except Exception as exc:
            logger.error(f"Erreur webhook vers {url}: {exc}")
            return False

    @classmethod
    def build_log_payload(cls, log_entry) -> dict:
        """
        Construit le payload standard pour un log.
        Format compatible avec la majorité des webhooks (Slack-like).
        """
        color = {
            "CRITICAL": "#FF0000",
            "ERROR":    "#F85149",
            "WARNING":  "#E3B341",
            "INFO":     "#388BFD",
            "DEBUG":    "#8B949E",
        }.get(log_entry.level, "#8B949E")

        return {
            "event":     "log.alert",
            "timestamp": timezone.now().isoformat(),
            "log": {
                "id":        log_entry.pk,
                "level":     log_entry.level,
                "message":   log_entry.message,
                "source":    log_entry.source.name if log_entry.source else None,
                "logger":    log_entry.logger_name or None,
                "timestamp": log_entry.timestamp.isoformat(),
                "traceback": bool(log_entry.traceback),
            },
            "color":     color,
            "dashboard": getattr(settings, "SITE_URL", "http://localhost:8000") + "/dashboard/",
        }

    @classmethod
    def build_alert_payload(cls, alert) -> dict:
        """Payload pour une alerte système."""
        return {
            "event":     "alert.triggered",
            "timestamp": timezone.now().isoformat(),
            "alert": {
                "id":          alert.pk,
                "title":       alert.title,
                "severity":    alert.severity,
                "source":      alert.source.name if alert.source else None,
                "description": alert.description,
                "triggered_at": alert.triggered_at.isoformat(),
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# Façade principale
# ══════════════════════════════════════════════════════════════════════════════

class NotificationService:
    """
    Point d'entrée unique pour toutes les notifications.
    Orchestre email + webhook selon la configuration.

    Configuration dans settings.py :
        NOTIFICATIONS_ENABLED = True
        WEBHOOK_URL = "https://hooks.slack.com/services/..."
        WEBHOOK_SECRET = "optional-hmac-secret"
        SITE_URL = "https://logmonitor.example.com"
    """

    @classmethod
    def _is_enabled(cls) -> bool:
        return getattr(settings, "NOTIFICATIONS_ENABLED", False)

    @classmethod
    def notify_log(cls, log_entry) -> None:
        """
        Déclenche les notifications pour un log entrant.
        Appelé depuis l'API d'ingestion après sauvegarde.
        Ne bloque jamais — les erreurs sont loggées silencieusement.
        """
        if not cls._is_enabled():
            return

        # Seulement pour ERROR et CRITICAL
        if log_entry.level not in ("ERROR", "CRITICAL", "WARNING"):
            return

        try:
            # ── Email ────────────────────────────────────────────────
            recipients = EmailNotifier.get_recipients_for_log(log_entry)
            if recipients:
                EmailNotifier.send_log_alert(log_entry, recipients)

            # ── Webhook ──────────────────────────────────────────────
            webhook_url = getattr(settings, "WEBHOOK_URL", "")
            if webhook_url and log_entry.level in ("ERROR", "CRITICAL"):
                payload = WebhookNotifier.build_log_payload(log_entry)
                WebhookNotifier.send(
                    webhook_url,
                    payload,
                    secret=getattr(settings, "WEBHOOK_SECRET", None),
                )
        except Exception as exc:
            # Ne jamais lever d'exception depuis le système de notification
            logger.exception(f"Erreur inattendue dans NotificationService.notify_log: {exc}")

    @classmethod
    def notify_alert(cls, alert) -> None:
        """Notifications pour une nouvelle alerte système."""
        if not cls._is_enabled():
            return

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            recipients = list(
                User.objects.filter(
                    is_active=True,
                    notify_on_error=True,
                    role__in=["admin", "analyst"],
                ).values_list("email", flat=True).exclude(email="")
            )
            EmailNotifier.send_alert_notification(alert, recipients)

            webhook_url = getattr(settings, "WEBHOOK_URL", "")
            if webhook_url and alert.severity in ("critical", "high"):
                payload = WebhookNotifier.build_alert_payload(alert)
                WebhookNotifier.send(webhook_url, payload)
        except Exception as exc:
            logger.exception(f"Erreur dans NotificationService.notify_alert: {exc}")
