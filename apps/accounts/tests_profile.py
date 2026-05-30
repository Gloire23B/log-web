"""
apps/accounts/tests_profile.py
─────────────────────────────────────────────────────────────────
Tests de la page profil utilisateur et du changement de mot de passe.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="profileuser", password="pass123",
            first_name="Jean", last_name="Test", email="jean@test.com"
        )
        self.url = reverse("accounts:profile")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/auth/login/?next={self.url}")

    def test_profile_page_loads(self):
        self.client.login(username="profileuser", password="pass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_shows_current_data(self):
        self.client.login(username="profileuser", password="pass123")
        response = self.client.get(self.url)
        self.assertContains(response, "Jean")
        self.assertContains(response, "jean@test.com")

    def test_profile_update_saves_changes(self):
        self.client.login(username="profileuser", password="pass123")
        response = self.client.post(self.url, {
            "first_name": "Pierre",
            "last_name": "Nouveau",
            "email": "pierre@test.com",
            "timezone": "Europe/Paris",
        })
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Pierre")
        self.assertEqual(self.user.email, "pierre@test.com")

    def test_profile_context_has_password_form(self):
        self.client.login(username="profileuser", password="pass123")
        response = self.client.get(self.url)
        self.assertIn("password_form", response.context)

    def test_profile_update_success_message(self):
        self.client.login(username="profileuser", password="pass123")
        self.client.post(self.url, {
            "first_name": "Claude",
            "last_name": "Test",
            "email": "claude@test.com",
            "timezone": "Europe/Paris",
        })
        response = self.client.get(self.url)
        messages = list(response.context["messages"])
        self.assertTrue(any("succès" in str(m) for m in messages))


class PasswordChangeViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="pwduser", password="oldpassword123"
        )
        self.url = reverse("accounts:change_password")

    def test_requires_authentication(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 302)

    def test_password_change_success(self):
        self.client.login(username="pwduser", password="oldpassword123")
        response = self.client.post(self.url, {
            "current_password": "oldpassword123",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword456"))

    def test_session_maintained_after_change(self):
        """L'utilisateur reste connecté après le changement de mot de passe."""
        self.client.login(username="pwduser", password="oldpassword123")
        self.client.post(self.url, {
            "current_password": "oldpassword123",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
        })
        # Doit pouvoir accéder à la page profil sans re-connexion
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)

    def test_wrong_current_password_fails(self):
        self.client.login(username="pwduser", password="oldpassword123")
        self.client.post(self.url, {
            "current_password": "wrongpassword",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
        })
        self.user.refresh_from_db()
        # Le mot de passe ne doit pas avoir changé
        self.assertTrue(self.user.check_password("oldpassword123"))

    def test_mismatched_passwords_fail(self):
        self.client.login(username="pwduser", password="oldpassword123")
        self.client.post(self.url, {
            "current_password": "oldpassword123",
            "new_password": "newpassword456",
            "confirm_password": "differentpassword",
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("oldpassword123"))

    def test_get_method_redirects(self):
        """GET sur l'endpoint de changement redirige vers le profil."""
        self.client.login(username="pwduser", password="oldpassword123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
