"""
apps/logs/tests_notifications.py
─────────────────────────────────────────────────────────────────
Tests du système de notifications email et webhook.
Utilise mock pour ne pas effectuer de vrais appels réseau.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.logs.models import LogEntry, LogSource
from apps.logs.notifications import (
    EmailNotifier, WebhookNotifier, NotificationService
)

User = get_user_model()


def make_log(level="ERROR"):
    src = LogSource.objects.create(name=f"notif-src-{level}", source_type="application")
    return LogEntry.objects.create(
        timestamp=timezone.now(),
        level=level,
        message=f"Test {level} log for notifications",
        source=src,
        traceback="Traceback: ..." if level in ("ERROR", "CRITICAL") else "",
    )


class EmailNotifierTest(TestCase):

    def setUp(self):
        self.user_notify = User.objects.create_user(
            username="notify_user", password="pass",
            email="notify@test.com", notify_on_error=True,
        )
        self.user_silent = User.objects.create_user(
            username="silent_user", password="pass",
            email="silent@test.com", notify_on_error=False,
        )

    def test_get_recipients_for_error_log(self):
        """Seuls les utilisateurs avec notify_on_error=True sont inclus."""
        log = make_log("ERROR")
        recipients = EmailNotifier.get_recipients_for_log(log)
        self.assertIn("notify@test.com", recipients)
        self.assertNotIn("silent@test.com", recipients)

    def test_get_recipients_for_info_log_is_empty(self):
        """Les logs INFO ne génèrent pas de notifications."""
        log = make_log("INFO")
        recipients = EmailNotifier.get_recipients_for_log(log)
        self.assertEqual(recipients, [])

    def test_get_recipients_excludes_empty_emails(self):
        """Les utilisateurs sans email sont exclus."""
        User.objects.create_user(username="noemail", password="pass",
                                  email="", notify_on_error=True)
        log = make_log("ERROR")
        recipients = EmailNotifier.get_recipients_for_log(log)
        self.assertNotIn("", recipients)

    @patch("apps.logs.notifications.send_mail")
    def test_send_log_alert_calls_send_mail(self, mock_send):
        """send_mail est appelé avec les bons paramètres."""
        log = make_log("CRITICAL")
        result = EmailNotifier.send_log_alert(log, ["admin@test.com"])
        self.assertTrue(mock_send.called)
        self.assertTrue(result)
        call_args = mock_send.call_args
        self.assertIn("CRITICAL", call_args.kwargs.get("subject", "") or call_args.args[0])

    @patch("apps.logs.notifications.send_mail")
    def test_send_log_alert_empty_recipients_returns_false(self, mock_send):
        """Sans destinataires, aucun email n'est envoyé."""
        log = make_log("ERROR")
        result = EmailNotifier.send_log_alert(log, [])
        self.assertFalse(result)
        mock_send.assert_not_called()

    @patch("apps.logs.notifications.send_mail", side_effect=Exception("SMTP down"))
    def test_send_log_alert_handles_exception(self, mock_send):
        """Les erreurs d'envoi sont capturées et retournent False."""
        log = make_log("ERROR")
        result = EmailNotifier.send_log_alert(log, ["admin@test.com"])
        self.assertFalse(result)

    @patch("apps.logs.notifications.send_mail")
    def test_warning_notified_for_users_with_notify_on_warning(self, mock_send):
        User.objects.create_user(
            username="warn_user", password="pass",
            email="warn@test.com", notify_on_warning=True, notify_on_error=False,
        )
        log = make_log("WARNING")
        recipients = EmailNotifier.get_recipients_for_log(log)
        self.assertIn("warn@test.com", recipients)


class WebhookNotifierTest(TestCase):

    def test_build_log_payload_structure(self):
        """Le payload log a la bonne structure."""
        log = make_log("ERROR")
        payload = WebhookNotifier.build_log_payload(log)
        self.assertEqual(payload["event"], "log.alert")
        self.assertIn("log", payload)
        self.assertEqual(payload["log"]["level"], "ERROR")
        self.assertIn("timestamp", payload)

    def test_build_alert_payload_structure(self):
        """Le payload alerte a la bonne structure."""
        from apps.alerts.models import Alert
        alert = Alert.objects.create(
            title="Test alert", severity="critical", status="active"
        )
        payload = WebhookNotifier.build_alert_payload(alert)
        self.assertEqual(payload["event"], "alert.triggered")
        self.assertIn("alert", payload)
        self.assertEqual(payload["alert"]["severity"], "critical")

    @patch("urllib.request.urlopen")
    def test_send_webhook_success(self, mock_urlopen):
        """Un webhook réussi retourne True."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = WebhookNotifier.send("https://hooks.example.com/test", {"event": "test"})
        self.assertTrue(result)
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_send_webhook_failure_returns_false(self, mock_urlopen):
        """Une erreur réseau retourne False sans lever d'exception."""
        result = WebhookNotifier.send("https://hooks.example.com/fail", {"event": "test"})
        self.assertFalse(result)

    def test_send_empty_url_returns_false(self):
        """Un URL vide retourne False immédiatement."""
        result = WebhookNotifier.send("", {"event": "test"})
        self.assertFalse(result)

    @patch("urllib.request.urlopen")
    def test_send_with_hmac_signature(self, mock_urlopen):
        """La signature HMAC est ajoutée si un secret est fourni."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        WebhookNotifier.send(
            "https://hooks.example.com/signed",
            {"event": "test"},
            secret="my-secret",
        )
        # Vérifie que la requête contient le header de signature
        req = mock_urlopen.call_args[0][0]
        self.assertIn("X-LogMonitor-Signature", req.headers)


@override_settings(NOTIFICATIONS_ENABLED=True, WEBHOOK_URL="", DEBUG=True)
class NotificationServiceTest(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_notif", password="pass",
            email="admin@notif.com", notify_on_error=True,
            role="admin",
        )

    @patch("apps.logs.notifications.EmailNotifier.send_log_alert")
    def test_notify_log_critical_triggers_email(self, mock_send):
        log = make_log("CRITICAL")
        NotificationService.notify_log(log)
        mock_send.assert_called_once()

    @patch("apps.logs.notifications.EmailNotifier.send_log_alert")
    def test_notify_log_info_does_not_trigger(self, mock_send):
        """Les logs INFO ne déclenchent pas de notification."""
        log = make_log("INFO")
        NotificationService.notify_log(log)
        mock_send.assert_not_called()

    @override_settings(NOTIFICATIONS_ENABLED=False)
    @patch("apps.logs.notifications.EmailNotifier.send_log_alert")
    def test_notifications_disabled_no_calls(self, mock_send):
        """Quand désactivé, aucune notification n'est envoyée."""
        log = make_log("CRITICAL")
        NotificationService.notify_log(log)
        mock_send.assert_not_called()

    @patch("apps.logs.notifications.EmailNotifier.send_log_alert",
           side_effect=Exception("Network error"))
    def test_notify_log_never_raises(self, mock_send):
        """Une exception interne ne se propage jamais à l'appelant."""
        log = make_log("ERROR")
        # Ne doit pas lever d'exception
        try:
            NotificationService.notify_log(log)
        except Exception:
            self.fail("notify_log a levé une exception inattendue")
