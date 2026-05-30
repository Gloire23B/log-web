"""apps/services/admin.py"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display  = ("name", "display_name", "service_type", "status_badge",
                     "avg_latency_ms", "error_rate", "uptime_30d", "last_check")
    list_filter   = ("service_type", "status", "is_active")
    search_fields = ("name", "display_name", "endpoint")
    ordering      = ("service_type", "name")

    @admin.display(description="Statut", ordering="status")
    def status_badge(self, obj):
        colors = {
            "operational": "#3fb950", "degraded": "#e3b341", "partial": "#f0883e",
            "major": "#f85149", "maintenance": "#388bfd", "unknown": "#8b949e"
        }
        c = colors.get(obj.status, "#8b949e")
        return format_html('<span style="color:{};font-weight:bold">● {}</span>', c, obj.get_status_display())
