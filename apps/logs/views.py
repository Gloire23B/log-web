"""
apps/logs/views.py
─────────────────────────────────────────────────────────────────
Vues de la page Logs détaillée.
- LogListView    : liste paginée avec filtres dynamiques HTMX
- LogDetailView  : détail d'un log avec traceback
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.http import HttpResponse
from django.db.models import Q
from django.template.loader import render_to_string
from django.conf import settings

from .models import LogEntry, LogSource


class LogListView(LoginRequiredMixin, ListView):
    """
    Liste paginée des logs avec filtres.
    HTMX : si requête partielle, retourne uniquement le tbody.
    """
    model = LogEntry
    template_name = "logs/log_list.html"
    context_object_name = "logs"
    login_url = "/auth/login/"
    paginate_by = getattr(settings, "LOGS_PER_PAGE", 50)

    def get_queryset(self):
        """
        Filtre les logs selon les paramètres GET.
        select_related("source") pour éviter N+1 sur la source.
        """
        qs = LogEntry.objects.select_related("source").all()

        level = self.request.GET.get("level", "")
        source_id = self.request.GET.get("source_id", "")
        search = self.request.GET.get("search", "").strip()
        date_from = self.request.GET.get("date_from", "")
        date_to = self.request.GET.get("date_to", "")
        resolved = self.request.GET.get("resolved", "")

        if level:
            qs = qs.filter(level=level)
        if source_id:
            qs = qs.filter(source_id=source_id)
        if search:
            qs = qs.filter(
                Q(message__icontains=search) |
                Q(source__name__icontains=search) |
                Q(logger_name__icontains=search) |
                Q(traceback__icontains=search)
            )
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        if resolved == "true":
            qs = qs.filter(is_resolved=True)
        elif resolved == "false":
            qs = qs.filter(is_resolved=False)

        return qs.order_by("-timestamp")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sources"] = LogSource.objects.filter(is_active=True).order_by("name")
        context["levels"] = LogEntry.Level.choices
        context["filters"] = {
            "level": self.request.GET.get("level", ""),
            "source_id": self.request.GET.get("source_id", ""),
            "search": self.request.GET.get("search", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
        }
        context["page_title"] = "Logs — LogMonitor"
        context["page_heading"] = "Explorateur de Logs"
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Si requête HTMX → retourne uniquement le partial du tableau.
        Sinon → page complète.
        """
        if self.request.htmx:
            html = render_to_string(
                "partials/log_table_rows.html",
                {"recent_logs": context["logs"]},
                request=self.request,
            )
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


class LogDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une entrée de log avec traceback et métadonnées."""
    model = LogEntry
    template_name = "logs/log_detail.html"
    context_object_name = "log"
    login_url = "/auth/login/"

    def get_queryset(self):
        return LogEntry.objects.select_related("source").all()
