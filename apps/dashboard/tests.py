"""
apps/dashboard/tests.py
─────────────────────────────────────────────────────────────────
Tests unitaires et d'intégration — App Dashboard.
Couvre : DashboardView (KPIs), RecentLogsHtmxView, LogVolumeChartView.
"""

import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from apps.logs.models import LogEntry, LogSource
from apps.alerts.models import Alert

User = get_user_model()


def create_log(level=LogEntry.Level.INFO, message="Test", hours_ago=1, source=None):
    return LogEntry.objects.create(
        timestamp=timezone.now() - timedelta(hours=hours_ago),
        level=level,
        message=message,
        source=source,
    )


class DashboardViewTest(TestCase):
    """Tests de la vue principale du dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="dashuser", password="pass123")
        self.url = reverse("dashboard:index")

    def test_redirects_unauthenticated(self):
        """Les visiteurs non connectés sont redirigés vers login."""
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_dashboard_loads_for_authenticated_user(self):
        """Le dashboard se charge pour un utilisateur connecté."""
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")

    def test_kpi_total_24h_counts_only_last_24h(self):
        """total_24h ne compte que les logs des 24 dernières heures."""
        create_log(hours_ago=1)   # dans les 24h ✓
        create_log(hours_ago=12)  # dans les 24h ✓
        LogEntry.objects.create(  # hors 24h ✗
            timestamp=timezone.now() - timedelta(hours=25),
            level=LogEntry.Level.INFO,
            message="Old log",
        )
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["total_24h"], 2)

    def test_kpi_error_count_includes_critical(self):
        """error_count inclut ERROR et CRITICAL."""
        create_log(LogEntry.Level.ERROR, hours_ago=2)
        create_log(LogEntry.Level.CRITICAL, hours_ago=3)
        create_log(LogEntry.Level.WARNING, hours_ago=1)  # ne doit pas compter
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["error_count"], 2)

    def test_kpi_warning_count(self):
        """warning_count ne compte que les WARNING."""
        create_log(LogEntry.Level.WARNING, hours_ago=1)
        create_log(LogEntry.Level.WARNING, hours_ago=2)
        create_log(LogEntry.Level.ERROR, hours_ago=1)
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["warning_count"], 2)

    def test_chart_data_json_in_context(self):
        """Le contexte contient les données JSON du graphique."""
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("chart_data_json", response.context)
        # Doit être du JSON valide
        data = json.loads(response.context["chart_data_json"])
        self.assertIn("labels", data)
        self.assertIn("datasets", data)
        self.assertEqual(len(data["datasets"]), 3)  # Erreurs, Warnings, Info

    def test_chart_data_has_24_labels(self):
        """Le graphique par défaut (24h) a 24 points."""
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        data = json.loads(response.context["chart_data_json"])
        self.assertEqual(len(data["labels"]), 24)

    def test_health_status_healthy_with_no_errors(self):
        """Statut 'healthy' quand il n'y a pas d'erreurs."""
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["health_status"]["status"], "healthy")

    def test_health_status_critical_with_many_errors(self):
        """Statut 'critical' avec beaucoup d'erreurs."""
        for _ in range(101):
            create_log(LogEntry.Level.ERROR, hours_ago=1)
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["health_status"]["status"], "critical")

    def test_context_contains_recent_logs(self):
        """Le contexte contient les logs récents."""
        create_log(hours_ago=1)
        create_log(hours_ago=2)
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("recent_logs", response.context)

    def test_recent_logs_limited_to_20(self):
        """La liste des logs récents est limitée à 20 entrées."""
        for i in range(25):
            create_log(hours_ago=1, message=f"Log {i}")
        self.client.login(username="dashuser", password="pass123")
        response = self.client.get(self.url)
        self.assertLessEqual(len(response.context["recent_logs"]), 20)


class RecentLogsHtmxViewTest(TestCase):
    """Tests de l'endpoint HTMX de rafraîchissement des logs."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="htmxuser", password="pass123")
        self.url = reverse("dashboard:htmx_recent_logs")
        self.source = LogSource.objects.create(
            name="htmx-server", source_type=LogSource.SourceType.SERVER
        )

    def test_returns_200_for_authenticated(self):
        """L'endpoint répond 200 pour un utilisateur connecté."""
        self.client.login(username="htmxuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_requires_authentication(self):
        """L'endpoint requiert une authentification."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_filter_by_level(self):
        """Le filtre par niveau fonctionne sur l'endpoint HTMX."""
        create_log(LogEntry.Level.ERROR, hours_ago=1)
        create_log(LogEntry.Level.INFO, hours_ago=1)
        self.client.login(username="htmxuser", password="pass123")
        response = self.client.get(self.url + "?level=ERROR")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("ERROR", content)
        self.assertNotIn("INFO", content)

    def test_filter_by_search(self):
        """La recherche fonctionne sur l'endpoint HTMX."""
        create_log(LogEntry.Level.INFO, "Message unique XYZ123", hours_ago=1)
        create_log(LogEntry.Level.INFO, "Autre message", hours_ago=1)
        self.client.login(username="htmxuser", password="pass123")
        response = self.client.get(self.url + "?search=XYZ123")
        content = response.content.decode()
        self.assertIn("XYZ123", content)
        self.assertNotIn("Autre message", content)

    def test_returns_html_not_json(self):
        """L'endpoint retourne du HTML (pas du JSON)."""
        self.client.login(username="htmxuser", password="pass123")
        response = self.client.get(self.url)
        content_type = response.get("Content-Type", "")
        self.assertIn("text/html", content_type)


class LogVolumeChartViewTest(TestCase):
    """Tests de l'endpoint JSON du graphique de volume."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="chartuser", password="pass123")
        self.url = reverse("dashboard:htmx_chart_volume")

    def test_returns_valid_json(self):
        """L'endpoint retourne du JSON valide."""
        self.client.login(username="chartuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("labels", data)
        self.assertIn("datasets", data)

    def test_period_24h_default(self):
        """La période par défaut est 24h avec 24 labels."""
        self.client.login(username="chartuser", password="pass123")
        response = self.client.get(self.url + "?period=24h")
        data = json.loads(response.content)
        self.assertEqual(len(data["labels"]), 24)

    def test_period_7d(self):
        """La période 7j retourne plus de points."""
        self.client.login(username="chartuser", password="pass123")
        response = self.client.get(self.url + "?period=7d")
        data = json.loads(response.content)
        self.assertGreater(len(data["labels"]), 24)

    def test_datasets_have_three_entries(self):
        """Les données contiennent 3 datasets (Erreurs, Warnings, Info)."""
        self.client.login(username="chartuser", password="pass123")
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(len(data["datasets"]), 3)

    def test_requires_authentication(self):
        """L'endpoint JSON requiert une authentification."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
