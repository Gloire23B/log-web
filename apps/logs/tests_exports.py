"""
apps/logs/tests_exports.py
─────────────────────────────────────────────────────────────────
Tests des exports CSV et JSON.
"""

import csv
import json
import io
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.logs.models import LogEntry, LogSource

User = get_user_model()


def make_log(level="INFO", message="Test", hours_ago=1, source=None):
    return LogEntry.objects.create(
        timestamp=timezone.now() - timezone.timedelta(hours=hours_ago),
        level=level, message=message, source=source,
    )


class LogExportCSVTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="csvuser", password="pass123")
        self.url = reverse("logs:export_csv")
        self.src = LogSource.objects.create(name="export-src", source_type="application")
        make_log("ERROR", "Error message", source=self.src)
        make_log("INFO",  "Info message")
        make_log("WARNING", "Warn message")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_returns_csv_content_type(self):
        self.client.login(username="csvuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("text/csv", response.get("Content-Type", ""))

    def test_csv_has_correct_disposition(self):
        self.client.login(username="csvuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("attachment", response.get("Content-Disposition", ""))
        self.assertIn(".csv", response.get("Content-Disposition", ""))

    def test_csv_has_header_row(self):
        self.client.login(username="csvuser", password="pass123")
        response = self.client.get(self.url)
        content = b"".join(response.streaming_content).decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        self.assertIn("Niveau", header)
        self.assertIn("Message", header)
        self.assertIn("Source", header)

    def test_csv_contains_all_logs(self):
        self.client.login(username="csvuser", password="pass123")
        response = self.client.get(self.url)
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Error message", content)
        self.assertIn("Info message", content)
        self.assertIn("Warn message", content)

    def test_csv_filter_by_level(self):
        self.client.login(username="csvuser", password="pass123")
        response = self.client.get(self.url + "?level=ERROR")
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Error message", content)
        self.assertNotIn("Info message", content)

    def test_csv_source_name_exported(self):
        self.client.login(username="csvuser", password="pass123")
        response = self.client.get(self.url)
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("export-src", content)


class LogExportJSONTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="jsonuser", password="pass123")
        self.url = reverse("logs:export_json")
        make_log("ERROR", "JSON error log")
        make_log("INFO",  "JSON info log")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_returns_json_content_type(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("application/json", response.get("Content-Type", ""))

    def test_json_has_correct_disposition(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn(".json", response.get("Content-Disposition", ""))

    def test_json_structure(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertIn("export_meta", data)
        self.assertIn("logs", data)

    def test_json_meta_contains_exporter(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data["export_meta"]["exported_by"], "jsonuser")

    def test_json_logs_have_required_fields(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertGreater(len(data["logs"]), 0)
        log = data["logs"][0]
        for field in ["id", "timestamp", "level", "message", "is_resolved"]:
            self.assertIn(field, log)

    def test_json_filter_by_level(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url + "?level=ERROR")
        data = json.loads(response.content)
        levels = [l["level"] for l in data["logs"]]
        self.assertTrue(all(l == "ERROR" for l in levels))

    def test_json_total_count_in_meta(self):
        self.client.login(username="jsonuser", password="pass123")
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data["export_meta"]["total_count"], len(data["logs"]))
