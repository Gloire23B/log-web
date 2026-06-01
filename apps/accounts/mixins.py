"""
apps/accounts/mixins.py
─────────────────────────────────────────────────────────────────
Mixins de contrôle d'accès basés sur le rôle (RBAC).
"""

from django.contrib import messages
from django.shortcuts import redirect


class MonitoringOnlyMixin:
    """
    Interdit l'accès aux utilisateurs avec le rôle 'user' (Utilisateur standard).
    Redirige vers le dashboard avec un message d'erreur.
    Doit être placé avant LoginRequiredMixin dans l'héritage.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == "user":
            messages.error(
                request,
                "Accès réservé aux administrateurs et analystes.",
            )
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)


class AdminOnlyMixin:
    """
    Réserve l'accès aux utilisateurs ayant le rôle 'admin' uniquement.
    Redirige vers le dashboard avec un message d'erreur pour les autres rôles.
    Doit être placé avant LoginRequiredMixin dans l'héritage.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != "admin":
            messages.error(
                request,
                "Accès réservé aux administrateurs.",
            )
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)
