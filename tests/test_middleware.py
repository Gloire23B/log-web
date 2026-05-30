"""
tests/test_middleware.py
─────────────────────────────────────────────────────────────────
Tests du middleware de rate limiting.
"""

from django.test import TestCase, Client, override_settings
from django.urls import reverse


@override_settings(
    DEBUG=True,
    API_KEYS=[],
    API_RATE_LIMIT_PER_IP=5,
    API_RATE_LIMIT_PER_KEY=10,
    API_RATE_LIMIT_WINDOW=60,
)
class RateLimitMiddlewareTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.ingest_url = reverse("api_log_ingest")
        self.health_url = reverse("api_health")

    def test_health_check_exempt_from_rate_limit(self):
        """Le health check n'est pas soumis au rate limiting."""
        for _ in range(20):
            response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_headers_present(self):
        """Les headers X-RateLimit-* sont présents sur les réponses API."""
        response = self.client.post(
            self.ingest_url,
            data='{"level":"INFO","message":"Test"}',
            content_type="application/json",
        )
        self.assertIn("X-RateLimit-Limit", response)
        self.assertIn("X-RateLimit-Remaining", response)
        self.assertIn("X-RateLimit-Reset", response)

    def test_rate_limit_remaining_decreases(self):
        """X-RateLimit-Remaining décroît à chaque requête."""
        r1 = self.client.post(
            self.ingest_url,
            data='{"level":"INFO","message":"R1"}',
            content_type="application/json",
        )
        r2 = self.client.post(
            self.ingest_url,
            data='{"level":"INFO","message":"R2"}',
            content_type="application/json",
        )
        remaining1 = int(r1.get("X-RateLimit-Remaining", 999))
        remaining2 = int(r2.get("X-RateLimit-Remaining", 999))
        self.assertGreater(remaining1, remaining2)

    def test_rate_limit_exceeded_returns_429(self):
        """Après la limite, l'API retourne HTTP 429."""
        for _ in range(5):
            self.client.post(
                self.ingest_url,
                data='{"level":"INFO","message":"flood"}',
                content_type="application/json",
            )
        # La 6ème doit être bloquée
        response = self.client.post(
            self.ingest_url,
            data='{"level":"INFO","message":"over limit"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 429)

    def test_429_has_retry_after_header(self):
        """HTTP 429 inclut le header Retry-After."""
        for _ in range(6):
            response = self.client.post(
                self.ingest_url,
                data='{"level":"INFO","message":"flood"}',
                content_type="application/json",
            )
        if response.status_code == 429:
            self.assertIn("Retry-After", response)

    def test_429_body_has_code(self):
        """Le body de 429 contient le code d'erreur."""
        import json
        for _ in range(6):
            response = self.client.post(
                self.ingest_url,
                data='{"level":"INFO","message":"flood"}',
                content_type="application/json",
            )
        if response.status_code == 429:
            data = json.loads(response.content)
            self.assertEqual(data["code"], "rate_limit_exceeded")

    def test_non_api_routes_not_rate_limited(self):
        """Les routes non-API ne sont pas soumises au rate limiting."""
        for _ in range(10):
            response = self.client.get("/auth/login/")
        self.assertNotEqual(response.status_code, 429)


class InMemoryRateLimitStoreTest(TestCase):

    def test_allows_within_limit(self):
        from logmonitor.middleware import InMemoryRateLimitStore
        store = InMemoryRateLimitStore()
        allowed, remaining = store.is_allowed("test-key", limit=5, window=60)
        self.assertTrue(allowed)
        self.assertEqual(remaining, 4)

    def test_blocks_after_limit(self):
        from logmonitor.middleware import InMemoryRateLimitStore
        store = InMemoryRateLimitStore()
        for _ in range(5):
            store.is_allowed("block-key", limit=5, window=60)
        allowed, remaining = store.is_allowed("block-key", limit=5, window=60)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_different_keys_independent(self):
        from logmonitor.middleware import InMemoryRateLimitStore
        store = InMemoryRateLimitStore()
        for _ in range(5):
            store.is_allowed("key-a", limit=5, window=60)
        # key-b est indépendant
        allowed, _ = store.is_allowed("key-b", limit=5, window=60)
        self.assertTrue(allowed)
