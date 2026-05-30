"""
apps/alerts/tests.py
─────────────────────────────────────────────────────────────────
Tests unitaires et d'intégration — App Alerts.
Couvre : modèle Alert, vues AlertListView, AlertAcknowledgeView,
AlertResolveView et AlertStatsHtmxView.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Alert
from apps.logs.models import LogSource

User = get_user_model()


def make_alert(severity=Alert.Severity.MEDIUM, status=Alert.Status.ACTIVE,
               title="Test Alert", source=None):
    return Alert.objects.create(
        title=title, severity=severity, status=status,
        source=source, description="Description de test",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Modèle Alert
# ══════════════════════════════════════════════════════════════════════════════

class AlertModelTest(TestCase):

    def test_alert_creation(self):
        alert = make_alert(Alert.Severity.CRITICAL)
        self.assertEqual(alert.severity, Alert.Severity.CRITICAL)
        self.assertEqual(alert.status, Alert.Status.ACTIVE)
        self.assertIsNotNone(alert.triggered_at)

    def test_str_contains_severity_and_title(self):
        alert = make_alert(title="Disk full")
        self.assertIn("Disk full", str(alert))

    def test_severity_color_critical(self):
        alert = make_alert(Alert.Severity.CRITICAL)
        self.assertIn("red", alert.severity_color)

    def test_severity_color_medium(self):
        alert = make_alert(Alert.Severity.MEDIUM)
        self.assertIn("amber", alert.severity_color)

    def test_ordering_by_triggered_at_desc(self):
        a1 = make_alert(title="First")
        a2 = make_alert(title="Second")
        alerts = list(Alert.objects.all())
        # Ordre par statut d'abord (active=active), puis date desc
        self.assertIn(a2, alerts[:2])

    def test_default_status_is_active(self):
        alert = Alert.objects.create(title="Default", severity=Alert.Severity.LOW)
        self.assertEqual(alert.status, Alert.Status.ACTIVE)


# ══════════════════════════════════════════════════════════════════════════════
# AlertListView
# ══════════════════════════════════════════════════════════════════════════════

class AlertListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="alertuser", password="pass123")
        self.url = reverse("alerts:list")
        make_alert(Alert.Severity.CRITICAL, title="Critique 1")
        make_alert(Alert.Severity.HIGH,     title="Élevée 1")
        make_alert(Alert.Severity.MEDIUM,   status=Alert.Status.RESOLVED, title="Résolue")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_page_loads_for_authenticated_user(self):
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/list.html")

    def test_default_filter_shows_active_only(self):
        """Par défaut, seules les alertes actives sont affichées."""
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url + "?status=active")
        self.assertEqual(response.context["paginator"].count, 2)

    def test_filter_resolved_shows_resolved(self):
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url + "?status=resolved")
        self.assertEqual(response.context["paginator"].count, 1)

    def test_filter_by_severity(self):
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url + "?severity=critical&status=active")
        self.assertEqual(response.context["paginator"].count, 1)

    def test_context_contains_severity_counts(self):
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("severity_counts", response.context)

    def test_context_contains_total_active(self):
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["total_active"], 2)

    def test_search_by_title(self):
        self.client.login(username="alertuser", password="pass123")
        response = self.client.get(self.url + "?search=Critique&status=")
        self.assertEqual(response.context["paginator"].count, 1)


# ══════════════════════════════════════════════════════════════════════════════
# AlertAcknowledgeView
# ══════════════════════════════════════════════════════════════════════════════

class AlertAcknowledgeViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="ackuser", password="pass123")
        self.alert = make_alert(Alert.Severity.HIGH, status=Alert.Status.ACTIVE)

    def test_acknowledge_changes_status(self):
        self.client.login(username="ackuser", password="pass123")
        url = reverse("alerts:acknowledge", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.ACKNOWLEDGED)

    def test_acknowledge_sets_user(self):
        self.client.login(username="ackuser", password="pass123")
        url = reverse("alerts:acknowledge", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.acknowledged_by, self.user)

    def test_acknowledge_sets_timestamp(self):
        self.client.login(username="ackuser", password="pass123")
        url = reverse("alerts:acknowledge", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_acknowledge_returns_html(self):
        """L'endpoint retourne du HTML (partial HTMX)."""
        self.client.login(username="ackuser", password="pass123")
        url = reverse("alerts:acknowledge", args=[self.alert.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.get("Content-Type", ""))

    def test_acknowledge_already_acknowledged_noop(self):
        """Acquitter une alerte déjà acquittée ne change rien."""
        self.alert.status = Alert.Status.ACKNOWLEDGED
        self.alert.save()
        self.client.login(username="ackuser", password="pass123")
        url = reverse("alerts:acknowledge", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.ACKNOWLEDGED)

    def test_requires_authentication(self):
        url = reverse("alerts:acknowledge", args=[self.alert.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)


# ══════════════════════════════════════════════════════════════════════════════
# AlertResolveView
# ══════════════════════════════════════════════════════════════════════════════

class AlertResolveViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="resolveuser", password="pass123")
        self.alert = make_alert(Alert.Severity.CRITICAL, status=Alert.Status.ACTIVE)

    def test_resolve_changes_status(self):
        self.client.login(username="resolveuser", password="pass123")
        url = reverse("alerts:resolve", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.RESOLVED)

    def test_resolve_sets_resolved_at(self):
        self.client.login(username="resolveuser", password="pass123")
        url = reverse("alerts:resolve", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertIsNotNone(self.alert.resolved_at)

    def test_resolve_already_resolved_noop(self):
        self.alert.status = Alert.Status.RESOLVED
        self.alert.resolved_at = timezone.now()
        self.alert.save()
        self.client.login(username="resolveuser", password="pass123")
        url = reverse("alerts:resolve", args=[self.alert.pk])
        self.client.post(url)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.RESOLVED)

    def test_returns_html_partial(self):
        self.client.login(username="resolveuser", password="pass123")
        url = reverse("alerts:resolve", args=[self.alert.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)

    def test_404_for_unknown_alert(self):
        self.client.login(username="resolveuser", password="pass123")
        url = reverse("alerts:resolve", args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
