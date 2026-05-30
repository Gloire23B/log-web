"""
apps/accounts/urls.py — Routes d'authentification
"""
from django.urls import path
from . import views
from .profile import ProfileView, PasswordChangeView

app_name = "accounts"

urlpatterns = [
    path("login/",           views.LoginView.as_view(),       name="login"),
    path("logout/",          views.LogoutView.as_view(),      name="logout"),
    path("profile/",         ProfileView.as_view(),           name="profile"),
    path("profile/password/",PasswordChangeView.as_view(),    name="change_password"),
]
