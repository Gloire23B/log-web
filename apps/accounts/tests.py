"""
apps/accounts/tests.py
─────────────────────────────────────────────────────────────────
Tests unitaires et d'intégration — App Accounts.
Couvre : modèle User, formulaire LoginForm, vues Login/Logout.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# Modèle User
# ══════════════════════════════════════════════════════════════════════════════

class UserModelTest(TestCase):
    """Tests du modèle User personnalisé."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            first_name="Jean",
            last_name="Dupont",
            role=User.Role.ANALYST,
        )

    def test_user_creation(self):
        """L'utilisateur est créé avec les bons attributs."""
        self.assertEqual(self.user.username, "testuser")
        self.assertEqual(self.user.role, User.Role.ANALYST)
        self.assertTrue(self.user.check_password("testpass123"))

    def test_display_name_with_full_name(self):
        """display_name retourne le nom complet si disponible."""
        self.assertEqual(self.user.display_name, "Jean Dupont")

    def test_display_name_fallback_to_username(self):
        """display_name retourne le username si pas de nom complet."""
        user = User.objects.create_user(username="noname", password="pass123")
        self.assertEqual(user.display_name, "noname")

    def test_initials_with_full_name(self):
        """Les initiales sont correctement calculées."""
        self.assertEqual(self.user.initials, "JD")

    def test_initials_fallback(self):
        """Initiales basées sur le username si pas de nom."""
        user = User.objects.create_user(username="admin", password="pass123")
        self.assertEqual(user.initials, "AD")

    def test_is_admin_user_for_superuser(self):
        """Un superuser est considéré comme admin."""
        user = User.objects.create_superuser(
            username="super", password="superpass", email="super@test.com"
        )
        self.assertTrue(user.is_admin_user)

    def test_is_admin_user_for_admin_role(self):
        """Un utilisateur avec rôle ADMIN est considéré admin."""
        user = User.objects.create_user(
            username="adminuser", password="pass", role=User.Role.ADMIN
        )
        self.assertTrue(user.is_admin_user)

    def test_viewer_cannot_manage_logs(self):
        """Un viewer ne peut pas gérer les logs."""
        user = User.objects.create_user(
            username="viewer", password="pass", role=User.Role.VIEWER
        )
        self.assertFalse(user.can_manage_logs)

    def test_analyst_can_manage_logs(self):
        """Un analyst peut gérer les logs."""
        self.assertTrue(self.user.can_manage_logs)

    def test_str_representation(self):
        """La représentation str inclut le nom et le rôle."""
        self.assertIn("Jean Dupont", str(self.user))
        self.assertIn("Analyste", str(self.user))

    def test_default_role_is_viewer(self):
        """Le rôle par défaut est Viewer."""
        user = User.objects.create_user(username="newuser", password="pass")
        self.assertEqual(user.role, User.Role.VIEWER)


# ══════════════════════════════════════════════════════════════════════════════
# Vues d'authentification
# ══════════════════════════════════════════════════════════════════════════════

class LoginViewTest(TestCase):
    """Tests de la vue de connexion."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("accounts:login")
        self.dashboard_url = reverse("dashboard:index")
        self.user = User.objects.create_user(
            username="loginuser",
            password="correctpassword",
        )

    def test_login_page_accessible(self):
        """La page de connexion est accessible (HTTP 200)."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_login_page_uses_correct_template(self):
        """La page de connexion utilise le bon template."""
        response = self.client.get(self.login_url)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_page_contains_form(self):
        """La page de connexion contient un formulaire."""
        response = self.client.get(self.login_url)
        self.assertContains(response, "<form")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_successful_login_redirects_to_dashboard(self):
        """Une connexion réussie redirige vers le dashboard."""
        response = self.client.post(self.login_url, {
            "username": "loginuser",
            "password": "correctpassword",
        })
        self.assertRedirects(response, self.dashboard_url)

    def test_failed_login_shows_error(self):
        """Un mauvais mot de passe affiche une erreur."""
        response = self.client.post(self.login_url, {
            "username": "loginuser",
            "password": "wrongpassword",
        })
        self.assertEqual(response.status_code, 200)
        # Le formulaire doit contenir des erreurs
        self.assertTrue(response.context["form"].errors)

    def test_failed_login_stays_on_login_page(self):
        """Échec de connexion → reste sur la page login."""
        response = self.client.post(self.login_url, {
            "username": "wrong",
            "password": "wrong",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_authenticated_user_redirected(self):
        """Un utilisateur déjà connecté est redirigé depuis la page login."""
        self.client.login(username="loginuser", password="correctpassword")
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.dashboard_url)

    def test_remember_me_session_expiry(self):
        """Sans 'remember me', la session expire à la fermeture."""
        self.client.post(self.login_url, {
            "username": "loginuser",
            "password": "correctpassword",
            "remember_me": False,
        })
        session = self.client.session
        self.assertEqual(session.get_expiry_age(), 0)

    def test_csrf_protection_active(self):
        """La protection CSRF est active sur le formulaire login."""
        response = self.client.get(self.login_url)
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_logout_requires_post(self):
        """La déconnexion nécessite une requête POST (sécurité CSRF)."""
        self.client.login(username="loginuser", password="correctpassword")
        # GET ne devrait pas déconnecter
        self.client.get(reverse("accounts:logout"))
        # L'utilisateur doit toujours être connecté
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_logout_via_post(self):
        """La déconnexion via POST fonctionne et redirige."""
        self.client.login(username="loginuser", password="correctpassword")
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, self.login_url)
