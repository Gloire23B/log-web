"""
apps/servers/tests.py
─────────────────────────────────────────────────────────────────
Tests — App Servers. Couvre : modèle Server, ServerListView.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from .models import Server

User = get_user_model()


def make_server(name="test-server", status=Server.Status.ONLINE,
                cpu=50.0, mem=60.0, disk=40.0, env=Server.Environment.PRODUCTION):
    return Server.objects.create(
        name=name, status=status, environment=env,
        ip_address="10.0.0.1", cpu_percent=cpu,
        memory_percent=mem, disk_percent=disk,
        last_seen=timezone.now(),
    )


class ServerModelTest(TestCase):

    def test_server_creation(self):
        s = make_server()
        self.assertEqual(s.name, "test-server")
        self.assertTrue(s.is_active)

    def test_str_contains_name(self):
        s = make_server("web-01")
        self.assertIn("web-01", str(s))

    def test_status_dot_online(self):
        s = make_server(status=Server.Status.ONLINE)
        self.assertIn("emerald", s.status_dot)

    def test_status_dot_critical_animates(self):
        s = make_server(status=Server.Status.CRITICAL)
        self.assertIn("animate-pulse", s.status_dot)

    def test_cpu_color_critical(self):
        s = make_server(cpu=95.0)
        self.assertIn("red", s.cpu_color)

    def test_cpu_color_warning(self):
        s = make_server(cpu=80.0)
        self.assertIn("amber", s.cpu_color)

    def test_cpu_color_ok(self):
        s = make_server(cpu=50.0)
        self.assertIn("emerald", s.cpu_color)

    def test_disk_color_critical(self):
        s = make_server(disk=92.0)
        self.assertIn("red", s.disk_color)

    def test_uptime_display_days(self):
        s = make_server()
        s.uptime_seconds = 86400 * 3 + 7200  # 3j 2h
        self.assertIn("3j", s.uptime_display)

    def test_uptime_display_hours_only(self):
        s = make_server()
        s.uptime_seconds = 7200  # 2h
        self.assertIn("2h", s.uptime_display)

    def test_uptime_display_none(self):
        s = make_server()
        s.uptime_seconds = None
        self.assertEqual(s.uptime_display, "—")

    def test_compute_status_online(self):
        s = make_server(cpu=50.0, mem=60.0, disk=40.0)
        s.last_seen = timezone.now()
        s.compute_status()
        self.assertEqual(s.status, Server.Status.ONLINE)

    def test_compute_status_warning_high_cpu(self):
        s = make_server(cpu=85.0, mem=60.0, disk=40.0)
        s.last_seen = timezone.now()
        s.compute_status()
        self.assertEqual(s.status, Server.Status.WARNING)

    def test_compute_status_critical_high_disk(self):
        s = make_server(cpu=50.0, mem=60.0, disk=96.0)
        s.last_seen = timezone.now()
        s.compute_status()
        self.assertEqual(s.status, Server.Status.CRITICAL)

    def test_compute_status_offline_stale(self):
        s = make_server()
        s.last_seen = timezone.now() - timedelta(minutes=10)
        s.compute_status()
        self.assertEqual(s.status, Server.Status.OFFLINE)

    def test_compute_status_unknown_no_last_seen(self):
        s = make_server()
        s.last_seen = None
        s.compute_status()
        self.assertEqual(s.status, Server.Status.UNKNOWN)


class ServerListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="srvuser", password="pass123")
        self.url = reverse("servers:list")
        make_server("prod-web-01", env=Server.Environment.PRODUCTION)
        make_server("prod-web-02", status=Server.Status.WARNING, env=Server.Environment.PRODUCTION)
        make_server("staging-app", env=Server.Environment.STAGING)

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_page_loads(self):
        self.client.login(username="srvuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "servers/list.html")

    def test_context_total(self):
        self.client.login(username="srvuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["total"], 3)

    def test_context_status_counts(self):
        self.client.login(username="srvuser", password="pass123")
        response = self.client.get(self.url)
        counts = response.context["status_counts"]
        self.assertEqual(counts.get("online", 0), 2)
        self.assertEqual(counts.get("warning", 0), 1)

    def test_servers_grouped_by_env(self):
        self.client.login(username="srvuser", password="pass123")
        response = self.client.get(self.url)
        by_env = response.context["servers_by_env"]
        self.assertIn("Production", by_env)
        self.assertEqual(len(by_env["Production"]), 2)

    def test_inactive_servers_excluded(self):
        Server.objects.create(
            name="inactive-srv", status=Server.Status.OFFLINE, is_active=False,
            last_seen=timezone.now(),
        )
        self.client.login(username="srvuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["total"], 3)
