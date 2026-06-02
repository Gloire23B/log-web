"""
apps/logs/views.py
─────────────────────────────────────────────────────────────────
Vues de la page Logs détaillée.
- LogListView       : liste paginée avec filtres dynamiques HTMX
- LogDetailView     : détail d'un log avec traceback
- LogResolveView    : bascule le statut résolu/non-résolu
- LogDeleteView     : suppression d'un log (admin)
- LogBulkActionView : résolution ou suppression groupée
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import DetailView, ListView
from django.conf import settings

from apps.accounts.mixins import AdminOnlyMixin
from .models import LogEntry, LogSource


class LogListView(LoginRequiredMixin, ListView):
    """Liste paginée des logs avec filtres. HTMX : retourne uniquement le tbody."""
    model = LogEntry
    template_name = "logs/log_list.html"
    context_object_name = "logs"
    login_url = "/auth/login/"
    paginate_by = getattr(settings, "LOGS_PER_PAGE", 50)

    def get_queryset(self):
        qs = LogEntry.objects.select_related("source").all()
        level     = self.request.GET.get("level", "")
        source_id = self.request.GET.get("source_id", "")
        search    = self.request.GET.get("search", "").strip()
        date_from = self.request.GET.get("date_from", "")
        date_to   = self.request.GET.get("date_to", "")
        resolved  = self.request.GET.get("resolved", "")

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
        context["sources"]      = LogSource.objects.filter(is_active=True).order_by("name")
        context["levels"]       = LogEntry.Level.choices
        context["filters"] = {
            "level":     self.request.GET.get("level", ""),
            "source_id": self.request.GET.get("source_id", ""),
            "search":    self.request.GET.get("search", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to":   self.request.GET.get("date_to", ""),
        }
        context["page_title"]   = "Logs — LogMonitor"
        context["page_heading"] = "Explorateur de Logs"
        return context

    def render_to_response(self, context, **response_kwargs):
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


class LogResolveView(LoginRequiredMixin, View):
    """Bascule le statut is_resolved d'un log (toggle)."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        log = get_object_or_404(LogEntry, pk=pk)
        log.is_resolved = not log.is_resolved
        log.save(update_fields=["is_resolved"])
        action = "résolu" if log.is_resolved else "réouvert"
        messages.success(request, f"Log #{pk} marqué comme {action}.")
        return redirect(request.META.get("HTTP_REFERER") or "logs:list")


class LogDeleteView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Suppression d'un log (admin uniquement)."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        log = get_object_or_404(LogEntry, pk=pk)
        log.delete()
        messages.success(request, f"Log #{pk} supprimé.")
        return redirect(request.META.get("HTTP_REFERER") or "logs:list")


class LogBulkActionView(LoginRequiredMixin, View):
    """Résolution ou suppression groupée de logs."""
    login_url = "/auth/login/"

    def post(self, request):
        action = request.POST.get("action")
        ids    = request.POST.getlist("log_ids")

        if not ids:
            messages.warning(request, "Aucun log sélectionné.")
            return redirect("logs:list")

        qs = LogEntry.objects.filter(pk__in=ids)

        if action == "resolve":
            count = qs.filter(is_resolved=False).update(is_resolved=True)
            messages.success(request, f"{count} log(s) marqué(s) comme résolu(s).")
        elif action == "delete" and request.user.role == "admin":
            count = qs.count()
            qs.delete()
            messages.success(request, f"{count} log(s) supprimé(s).")
        else:
            messages.error(request, "Action non autorisée.")

        return redirect("logs:list")
