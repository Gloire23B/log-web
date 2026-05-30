"""
apps/servers/views.py
─────────────────────────────────────────────────────────────────
Vue de monitoring des serveurs.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import Server


class ServerListView(LoginRequiredMixin, ListView):
    """
    Grille de monitoring des serveurs avec métriques en temps réel.
    Groupement par environnement (production en premier).
    """
    model = Server
    template_name = "servers/list.html"
    context_object_name = "servers"
    login_url = "/auth/login/"

    def get_queryset(self):
        return Server.objects.select_related("log_source").filter(
            is_active=True
        ).order_by("environment", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        servers = context["servers"]

        # Compteurs par statut
        status_counts = {}
        for s in Server.Status:
            status_counts[s.value] = sum(1 for srv in servers if srv.status == s.value)

        # Regroupement par environnement
        by_env = {}
        for srv in servers:
            env = srv.get_environment_display()
            by_env.setdefault(env, []).append(srv)

        context.update({
            "page_title": "Serveurs — LogMonitor",
            "status_counts": status_counts,
            "servers_by_env": by_env,
            "total": len(servers),
            "online_count": status_counts.get("online", 0),
            "critical_count": status_counts.get("critical", 0),
        })
        return context
