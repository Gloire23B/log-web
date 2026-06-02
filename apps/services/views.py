"""
apps/services/views.py
─────────────────────────────────────────────────────────────────
Vues de monitoring et gestion des services.
"""
import ssl
import time
import urllib.error
import urllib.request

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.accounts.mixins import AdminOnlyMixin, MonitoringOnlyMixin
from .forms import ServiceForm
from .models import Service


class ServiceListView(MonitoringOnlyMixin, LoginRequiredMixin, ListView):
    """Liste des services avec métriques de santé."""
    model = Service
    template_name = "services/list.html"
    context_object_name = "services"
    login_url = "/auth/login/"

    def get_queryset(self):
        return Service.objects.select_related("log_source").filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = context["services"]

        status_counts = {s.value: 0 for s in Service.Status}
        for svc in services:
            status_counts[svc.status] = status_counts.get(svc.status, 0) + 1

        by_type = {}
        for svc in services:
            t = svc.get_service_type_display()
            by_type.setdefault(t, []).append(svc)

        context.update({
            "page_title": "Services — LogMonitor",
            "page_heading": "Services",
            "status_counts": status_counts,
            "services_by_type": by_type,
            "total": len(services),
            "operational_count": status_counts.get("operational", 0),
            "create_form": ServiceForm(),
        })
        return context


class ServiceCreateView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Création d'un service depuis l'interface."""
    login_url = "/auth/login/"

    def post(self, request):
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Service « {service} » ajouté avec succès.")
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
        return redirect("services:list")


class ServiceEditView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Mise à jour d'un service existant."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f"Service « {service} » mis à jour.")
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
        return redirect("services:list")


class ServiceDeleteView(AdminOnlyMixin, LoginRequiredMixin, View):
    """Suppression d'un service."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        name = str(service)
        service.delete()
        messages.success(request, f"Service « {name} » supprimé.")
        return redirect("services:list")


class ServiceCheckView(MonitoringOnlyMixin, LoginRequiredMixin, View):
    """
    Vérifie dynamiquement la santé d'un service via son endpoint HTTP.
    Retourne le partial HTML de la carte (pour swap HTMX).
    """
    login_url = "/auth/login/"

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk)

        if not service.endpoint:
            service.status = Service.Status.UNKNOWN
            service.last_check = timezone.now()
            service.save(update_fields=["status", "last_check"])
        else:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                service.endpoint,
                headers={"User-Agent": "LogMonitor/1.0 HealthCheck"},
            )
            try:
                t0 = time.time()
                response = urllib.request.urlopen(req, timeout=10, context=ctx)
                latency = (time.time() - t0) * 1000
                code = response.status

                service.avg_latency_ms = round(latency, 1)
                service.last_check = timezone.now()
                if 200 <= code < 400:
                    service.status = Service.Status.OPERATIONAL
                elif 500 <= code < 600:
                    service.status = Service.Status.MAJOR
                else:
                    service.status = Service.Status.DEGRADED
                service.save(update_fields=["status", "avg_latency_ms", "last_check"])

            except urllib.error.HTTPError as exc:
                service.status = Service.Status.MAJOR if exc.code >= 500 else Service.Status.DEGRADED
                service.last_check = timezone.now()
                service.save(update_fields=["status", "last_check"])
            except Exception:
                service.status = Service.Status.MAJOR
                service.last_check = timezone.now()
                service.save(update_fields=["status", "last_check"])

        return render(request, "services/partials/card.html", {"svc": service})
