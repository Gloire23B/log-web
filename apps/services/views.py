"""apps/services/views.py"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Service


class ServiceListView(LoginRequiredMixin, ListView):
    model = Service
    template_name = "services/list.html"
    context_object_name = "services"
    login_url = "/auth/login/"

    def get_queryset(self):
        return Service.objects.select_related("log_source").filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = context["services"]
        from django.db.models import Count
        status_counts = {}
        for s in Service.Status:
            status_counts[s.value] = sum(1 for svc in services if svc.status == s.value)
        # Regroupement par type
        by_type = {}
        for svc in services:
            t = svc.get_service_type_display()
            by_type.setdefault(t, []).append(svc)
        context.update({
            "page_title": "Services — LogMonitor",
            "status_counts": status_counts,
            "services_by_type": by_type,
            "total": len(services),
            "operational_count": status_counts.get("operational", 0),
        })
        return context
