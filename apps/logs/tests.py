"""
apps/logs/tests.py
─────────────────────────────────────────────────────────────────
Tests unitaires et d'intégration — App Logs.
Couvre : modèles LogSource & LogEntry, vues LogListView & LogDetailView.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from .models import LogEntry, LogSource

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def create_log(level=LogEntry.Level.INFO, message="Test log", source=None, minutes_ago=0):
    """Factory helper pour créer un LogEntry."""
    return LogEntry.objects.create(
        timestamp=timezone.now() - timedelta(minutes=minutes_ago),
        level=level,
        message=message,
        source=source,
    )

def create_source(name="test-server"):
    return LogSource.objects.create(name=name, source_type=LogSource.SourceType.SERVER)


# ══════════════════════════════════════════════════════════════════════════════
# LogSource Model
# ══════════════════════════════════════════════════════════════════════════════

class LogSourceModelTest(TestCase):

    def test_source_creation(self):
        """Une source est créée avec les bons attributs."""
        source = LogSource.objects.create(
            name="api-gateway",
            source_type=LogSource.SourceType.SERVICE,
            hostname="10.0.0.1",
        )
        self.assertEqual(source.name, "api-gateway")
        self.assertEqual(source.source_type, LogSource.SourceType.SERVICE)
        self.assertTrue(source.is_active)

    def test_source_str(self):
        """__str__ contient le nom et le type."""
        source = create_source("prod-db")
        self.assertIn("prod-db", str(source))

    def test_source_name_unique(self):
        """Deux sources ne peuvent pas avoir le même nom."""
        create_source("unique-server")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            create_source("unique-server")

    def test_recent_error_count(self):
        """recent_error_count compte les erreurs des dernières 24h."""
        source = create_source("error-source")
        # 3 erreurs dans les 24h
        for _ in range(3):
            create_log(level=LogEntry.Level.ERROR, source=source, minutes_ago=60)
        # 1 erreur ancienne (> 24h)
        LogEntry.objects.create(
            timestamp=timezone.now() - timedelta(hours=25),
            level=LogEntry.Level.ERROR,
            message="old error",
            source=source,
        )
        self.assertEqual(source.recent_error_count, 3)


# ══════════════════════════════════════════════════════════════════════════════
# LogEntry Model
# ══════════════════════════════════════════════════════════════════════════════

class LogEntryModelTest(TestCase):

    def setUp(self):
        self.source = create_source()

    def test_log_creation(self):
        """Un log est créé avec les bons champs."""
        log = create_log(
            level=LogEntry.Level.ERROR,
            message="Connexion refusée",
            source=self.source,
        )
        self.assertEqual(log.level, LogEntry.Level.ERROR)
        self.assertEqual(log.message, "Connexion refusée")
        self.assertFalse(log.is_resolved)

    def test_log_str_contains_level_and_message(self):
        """__str__ contient le niveau et le message."""
        log = create_log(level=LogEntry.Level.WARNING, message="Mémoire faible")
        self.assertIn("WARNING", str(log))
        self.assertIn("Mémoire faible", str(log))

    def test_level_color_class_debug(self):
        log = create_log(level=LogEntry.Level.DEBUG)
        self.assertIn("slate", log.level_color_class)

    def test_level_color_class_error(self):
        log = create_log(level=LogEntry.Level.ERROR)
        self.assertIn("red", log.level_color_class)

    def test_level_color_class_critical(self):
        log = create_log(level=LogEntry.Level.CRITICAL)
        self.assertIn("red", log.level_color_class)
        self.assertIn("font-bold", log.level_color_class)

    def test_level_dot_class_critical_animates(self):
        log = create_log(level=LogEntry.Level.CRITICAL)
        self.assertIn("animate-pulse", log.level_dot_class)

    def test_has_traceback_false_when_empty(self):
        log = create_log()
        self.assertFalse(log.has_traceback)

    def test_has_traceback_true_when_set(self):
        log = LogEntry.objects.create(
            timestamp=timezone.now(),
            level=LogEntry.Level.ERROR,
            message="Erreur avec traceback",
            traceback="Traceback (most recent call last):\n  File ...",
        )
        self.assertTrue(log.has_traceback)

    def test_ordering_by_timestamp_desc(self):
        """Les logs sont triés par timestamp décroissant."""
        log1 = create_log(minutes_ago=10)
        log2 = create_log(minutes_ago=5)
        log3 = create_log(minutes_ago=1)
        logs = list(LogEntry.objects.all())
        self.assertEqual(logs[0], log3)
        self.assertEqual(logs[2], log1)

    def test_indexes_exist(self):
        """Les index définis existent dans les Meta."""
        index_names = [idx.name for idx in LogEntry._meta.indexes]
        self.assertIn("idx_level_timestamp", index_names)
        self.assertIn("idx_source_timestamp", index_names)
        self.assertIn("idx_timestamp", index_names)

    def test_extra_data_default_is_dict(self):
        """extra_data est un dict vide par défaut."""
        log = create_log()
        self.assertEqual(log.extra_data, {})
        self.assertIsInstance(log.extra_data, dict)


# ══════════════════════════════════════════════════════════════════════════════
# LogListView
# ══════════════════════════════════════════════════════════════════════════════

class LogListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.url = reverse("logs:list")
        self.source = create_source("web-server")
        # Créer des logs de test
        create_log(LogEntry.Level.ERROR, "Erreur critique", self.source)
        create_log(LogEntry.Level.INFO, "Démarrage service", self.source)
        create_log(LogEntry.Level.WARNING, "Disk space low")

    def test_redirects_unauthenticated(self):
        """Les utilisateurs non connectés sont redirigés vers login."""
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_authenticated_access(self):
        """Un utilisateur connecté accède à la liste des logs."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "logs/log_list.html")

    def test_all_logs_displayed(self):
        """Tous les logs créés sont visibles."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.context["paginator"].count, 3)

    def test_filter_by_level(self):
        """Le filtre par niveau fonctionne."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url + "?level=ERROR")
        self.assertEqual(response.context["paginator"].count, 1)

    def test_filter_by_search(self):
        """La recherche plein texte fonctionne."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url + "?search=Démarrage")
        self.assertEqual(response.context["paginator"].count, 1)

    def test_filter_by_source(self):
        """Le filtre par source fonctionne."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url + f"?source_id={self.source.pk}")
        # 2 logs avec cette source
        self.assertEqual(response.context["paginator"].count, 2)

    def test_context_contains_sources(self):
        """Le contexte contient la liste des sources."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("sources", response.context)

    def test_context_contains_levels(self):
        """Le contexte contient les choix de niveaux."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("levels", response.context)

    def test_htmx_request_returns_partial(self):
        """Une requête HTMX retourne uniquement le tableau partial."""
        self.client.login(username="testuser", password="pass123")
        response = self.client.get(
            self.url,
            HTTP_HX_REQUEST="true",
        )
        # Le partial ne doit pas contenir les balises HTML complètes
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<!DOCTYPE html>")


# ══════════════════════════════════════════════════════════════════════════════
# LogDetailView
# ══════════════════════════════════════════════════════════════════════════════

class LogDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="detailuser", password="pass123")
        self.log = create_log(
            level=LogEntry.Level.CRITICAL,
            message="Erreur fatale",
        )
        self.log.traceback = "Traceback:\n  File test.py, line 42"
        self.log.save()

    def test_detail_view_accessible(self):
        """La vue de détail est accessible pour un log existant."""
        self.client.login(username="detailuser", password="pass123")
        url = reverse("logs:detail", args=[self.log.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail_view_uses_correct_template(self):
        """La vue de détail utilise le bon template."""
        self.client.login(username="detailuser", password="pass123")
        url = reverse("logs:detail", args=[self.log.pk])
        response = self.client.get(url)
        self.assertTemplateUsed(response, "logs/log_detail.html")

    def test_detail_view_displays_message(self):
        """Le message du log est affiché."""
        self.client.login(username="detailuser", password="pass123")
        url = reverse("logs:detail", args=[self.log.pk])
        response = self.client.get(url)
        self.assertContains(response, "Erreur fatale")

    def test_detail_view_displays_traceback(self):
        """Le traceback est affiché quand il existe."""
        self.client.login(username="detailuser", password="pass123")
        url = reverse("logs:detail", args=[self.log.pk])
        response = self.client.get(url)
        self.assertContains(response, "Traceback")

    def test_detail_view_404_for_unknown_log(self):
        """Une 404 est retournée pour un log inexistant."""
        self.client.login(username="detailuser", password="pass123")
        url = reverse("logs:detail", args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_detail_redirects_unauthenticated(self):
        """Un utilisateur non connecté est redirigé."""
        url = reverse("logs:detail", args=[self.log.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
