"""
apps/accounts/urls.py — Routes d'authentification
"""
from django.urls import path
from . import views
from .profile import ProfileView, PasswordChangeView
from .user_management import (
    UserListView, UserCreateView, UserEditView,
    UserDeleteView, UserBulkDeleteView,
)

app_name = "accounts"

urlpatterns = [
    path("login/",                    views.LoginView.as_view(),        name="login"),
    path("register/",                 views.RegisterView.as_view(),     name="register"),
    path("logout/",                   views.LogoutView.as_view(),       name="logout"),
    path("profile/",                  ProfileView.as_view(),            name="profile"),
    path("profile/password/",         PasswordChangeView.as_view(),     name="change_password"),
    path("users/",                    UserListView.as_view(),           name="user_list"),
    path("users/create/",             UserCreateView.as_view(),         name="user_create"),
    path("users/<int:pk>/edit/",      UserEditView.as_view(),           name="user_edit"),
    path("users/<int:pk>/delete/",    UserDeleteView.as_view(),         name="user_delete"),
    path("users/bulk-delete/",        UserBulkDeleteView.as_view(),     name="user_bulk_delete"),
]
