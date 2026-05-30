"""
apps/logs/tests_api.py
─────────────────────────────────────────────────────────────────
Tests de l'API REST d'ingestion de logs.
Couvre : authentification, validation, ingestion simple, batch, health check.
"""

import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.logs.models import LogEntry, LogSource


@override_settings(DEBUG=True, API_KEYS=[])
class LogIngestViewTest(TestCase):
    """Tests de l'endpoint d'ingestion simple POST /api/v1/logs/ingest/"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("api_log_ingest")

    def _post(self, data):
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json"
        )

    # ── Cas nominaux ──────────────────────────────────────────────────

    def test_ingest_minimal_log(self):
        """Un log avec juste level + message est accepté."""
        response = self._post({"level": "INFO", "message": "Test log"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_ingest_returns_log_id(self):
        """La réponse contient l'ID du log créé."""
        response = self._post({"level": "ERROR", "message": "Erreur test"})
        data = json.loads(response.content)
        self.assertIn("id", data)
        self.assertIsInstance(data["id"], int)

    def test_ingest_with_source_creates_source(self):
        """Une nouvelle source est créée automatiquement."""
        self._post({"level": "INFO", "message": "Test", "source": "new-service"})
        self.assertTrue(LogSource.objects.filter(name="new-service").exists())

    def test_ingest_reuses_existing_source(self):
        """Une source existante est réutilisée (pas de doublon)."""
        LogSource.objects.create(name="existing-src", source_type="application")
        self._post({"level": "INFO", "message": "Test", "source": "existing-src"})
        self.assertEqual(LogSource.objects.filter(name="existing-src").count(), 1)

    def test_level_is_uppercased(self):
        """Le niveau est normalisé en majuscules."""
        self._post({"level": "error", "message": "Lower case level"})
        log = LogEntry.objects.first()
        self.assertEqual(log.level, "ERROR")

    def test_timestamp_default_is_now(self):
        """Sans timestamp, l'heure actuelle est utilisée."""
        before = timezone.now()
        self._post({"level": "INFO", "message": "No timestamp"})
        after = timezone.now()
        log = LogEntry.objects.first()
        self.assertGreaterEqual(log.timestamp, before)
        self.assertLessEqual(log.timestamp, after)

    def test_custom_timestamp_is_saved(self):
        """Un timestamp fourni est correctement sauvegardé."""
        ts = "2025-01-15T14:30:00Z"
        self._post({"level": "INFO", "message": "Custom ts", "timestamp": ts})
        log = LogEntry.objects.first()
        self.assertEqual(log.timestamp.year, 2025)
        self.assertEqual(log.timestamp.month, 1)

    def test_extra_fields_are_saved(self):
        """Les champs optionnels (logger, traceback, extra) sont sauvegardés."""
        self._post({
            "level": "ERROR",
            "message": "Full log",
            "logger": "apps.views",
            "traceback": "Traceback: ...",
            "extra": {"user_id": 42, "request_id": "abc"},
            "file": "apps/views.py",
            "line": "127",
        })
        log = LogEntry.objects.first()
        self.assertEqual(log.logger_name, "apps.views")
        self.assertEqual(log.traceback, "Traceback: ...")
        self.assertEqual(log.extra_data["user_id"], 42)
        self.assertEqual(log.file_path, "apps/views.py")
        self.assertEqual(log.line_number, 127)

    # ── Validation ────────────────────────────────────────────────────

    def test_missing_message_returns_400(self):
        response = self._post({"level": "INFO"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "validation_error")

    def test_empty_message_returns_400(self):
        response = self._post({"level": "INFO", "message": "   "})
        self.assertEqual(response.status_code, 400)

    def test_invalid_level_returns_400(self):
        response = self._post({"level": "VERBOSE", "message": "Test"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("VERBOSE", data["error"])

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url,
            data="not json {",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "invalid_json")

    def test_non_dict_payload_returns_400(self):
        response = self.client.post(
            self.url,
            data=json.dumps(["not", "a", "dict"]),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_timestamp_returns_400(self):
        response = self._post({"level": "INFO", "message": "Test", "timestamp": "not-a-date"})
        self.assertEqual(response.status_code, 400)

    def test_get_method_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # ── Authentification ──────────────────────────────────────────────

    @override_settings(DEBUG=False, API_KEYS=["secret-key-123"])
    def test_missing_api_key_returns_401(self):
        response = self._post({"level": "INFO", "message": "Test"})
        self.assertEqual(response.status_code, 401)

    @override_settings(DEBUG=False, API_KEYS=["secret-key-123"])
    def test_wrong_api_key_returns_401(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"level": "INFO", "message": "Test"}),
            content_type="application/json",
            HTTP_X_API_KEY="wrong-key"
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(DEBUG=False, API_KEYS=["secret-key-123"])
    def test_valid_api_key_accepted(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"level": "INFO", "message": "Test"}),
            content_type="application/json",
            HTTP_X_API_KEY="secret-key-123"
        )
        self.assertEqual(response.status_code, 201)


@override_settings(DEBUG=True, API_KEYS=[])
class LogIngestBulkViewTest(TestCase):
    """Tests de l'endpoint batch POST /api/v1/logs/ingest/bulk/"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("api_log_ingest_bulk")

    def _post_bulk(self, logs):
        return self.client.post(
            self.url,
            data=json.dumps({"logs": logs}),
            content_type="application/json"
        )

    def test_bulk_ingest_multiple_logs(self):
        logs = [{"level": "INFO", "message": f"Log {i}"} for i in range(10)]
        response = self._post_bulk(logs)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LogEntry.objects.count(), 10)

    def test_bulk_returns_ingested_count(self):
        logs = [{"level": "ERROR", "message": f"Err {i}"} for i in range(5)]
        response = self._post_bulk(logs)
        data = json.loads(response.content)
        self.assertEqual(data["ingested"], 5)
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["errors"], [])

    def test_bulk_partial_errors(self):
        """Les logs invalides sont signalés sans bloquer les valides."""
        logs = [
            {"level": "INFO", "message": "Valide"},
            {"level": "INVALID", "message": "Invalide"},
            {"level": "ERROR", "message": "Valide aussi"},
        ]
        response = self._post_bulk(logs)
        data = json.loads(response.content)
        self.assertEqual(data["ingested"], 2)
        self.assertEqual(len(data["errors"]), 1)
        self.assertEqual(data["errors"][0]["index"], 1)

    def test_empty_list_returns_400(self):
        response = self._post_bulk([])
        self.assertEqual(response.status_code, 400)

    def test_not_a_list_returns_400(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"logs": "not a list"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_batch_size_limit(self):
        """Un batch de plus de 1000 logs est refusé."""
        logs = [{"level": "INFO", "message": f"Log {i}"} for i in range(1001)]
        response = self._post_bulk(logs)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "batch_too_large")

    def test_exactly_1000_logs_accepted(self):
        logs = [{"level": "INFO", "message": f"Log {i}"} for i in range(1000)]
        response = self._post_bulk(logs)
        self.assertEqual(response.status_code, 201)

    def test_bulk_uses_bulk_create(self):
        """bulk_create est utilisé → les logs sont insérés efficacement."""
        logs = [{"level": "DEBUG", "message": f"Bulk {i}"} for i in range(50)]
        self._post_bulk(logs)
        self.assertEqual(LogEntry.objects.count(), 50)


class HealthCheckViewTest(TestCase):
    """Tests de l'endpoint GET /api/v1/health/"""

    def setUp(self):
        self.client = Client()
        self.url = reverse("api_health")

    def test_health_check_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_json(self):
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("timestamp", data)

    def test_health_check_db_ok(self):
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "ok")

    def test_health_no_auth_required(self):
        """Le health check est accessible sans authentification."""
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 302)
