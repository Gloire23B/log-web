"""
apps/services/tests.py
─────────────────────────────────────────────────────────────────
Tests — App Services. Couvre : modèle Service, ServiceListView.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Service

User = get_user_model()


def make_service(name="test-svc", status=Service.Status.OPERATIONAL,
                 stype=Service.ServiceType.API,
                 latency=120.0, err_rate=0.5, rps=500.0, uptime=99.99):
    return Service.objects.create(
        name=name, service_type=stype, status=status,
        avg_latency_ms=latency, error_rate=err_rate,
        requests_per_sec=rps, uptime_30d=uptime,
    )


class ServiceModelTest(TestCase):

    def test_creation(self):
        s = make_service()
        self.assertEqual(s.name, "test-svc")
        self.assertTrue(s.is_active)

    def test_str_uses_name(self):
        s = make_service(name="api-gateway")
        self.assertIn("api-gateway", str(s))

    def test_str_uses_display_name_if_set(self):
        s = Service.objects.create(
            name="api-gw", display_name="API Gateway",
            service_type=Service.ServiceType.API,
            status=Service.Status.OPERATIONAL,
        )
        self.assertEqual(str(s), "API Gateway")

    def test_status_color_operational(self):
        s = make_service()
        self.assertIn("emerald", s.status_color)

    def test_status_color_major(self):
        s = make_service(status=Service.Status.MAJOR)
        self.assertIn("red", s.status_color)

    def test_status_dot_degraded_animates(self):
        s = make_service(status=Service.Status.DEGRADED)
        self.assertIn("animate-pulse", s.status_dot)

    def test_latency_color_ok(self):
        s = make_service(latency=150.0)
        self.assertIn("emerald", s.latency_color)

    def test_latency_color_warning(self):
        s = make_service(latency=600.0)
        self.assertIn("amber", s.latency_color)

    def test_latency_color_critical(self):
        s = make_service(latency=1500.0)
        self.assertIn("red", s.latency_color)

    def test_error_rate_color_ok(self):
        s = make_service(err_rate=0.3)
        self.assertIn("emerald", s.error_rate_color)

    def test_error_rate_color_critical(self):
        s = make_service(err_rate=7.0)
        self.assertIn("red", s.error_rate_color)

    def test_none_latency_returns_safe_color(self):
        s = make_service(latency=None)
        s.avg_latency_ms = None
        self.assertIn("8B949E", s.latency_color)


class ServiceListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="svcuser", password="pass123")
        self.url = reverse("services:list")
        make_service("api-gw",   status=Service.Status.OPERATIONAL, stype=Service.ServiceType.API)
        make_service("auth-svc", status=Service.Status.DEGRADED,    stype=Service.ServiceType.API)
        make_service("cache",    status=Service.Status.OPERATIONAL,  stype=Service.ServiceType.CACHE)

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_page_loads(self):
        self.client.login(username="svcuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "services/list.html")

    def test_context_total(self):
        self.client.login(username="svcuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["total"], 3)

    def test_context_status_counts(self):
        self.client.login(username="svcuser", password="pass123")
        response = self.client.get(self.url)
        counts = response.context["status_counts"]
        self.assertEqual(counts.get("operational", 0), 2)
        self.assertEqual(counts.get("degraded", 0), 1)

    def test_services_grouped_by_type(self):
        self.client.login(username="svcuser", password="pass123")
        response = self.client.get(self.url)
        by_type = response.context["services_by_type"]
        self.assertIn("API REST", by_type)
        self.assertEqual(len(by_type["API REST"]), 2)

    def test_inactive_services_excluded(self):
        Service.objects.create(
            name="inactive-svc", is_active=False,
            status=Service.Status.UNKNOWN,
            service_type=Service.ServiceType.OTHER,
        )
        self.client.login(username="svcuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["total"], 3)
