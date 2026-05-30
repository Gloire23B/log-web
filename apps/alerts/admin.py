"""apps/alerts/admin.py"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display  = ("title", "severity_badge", "status_badge", "source", "triggered_at", "acknowledged_by")
    list_filter   = ("severity", "status", "triggered_at")
    search_fields = ("title", "description", "source__name")
    ordering      = ("-triggered_at",)
    readonly_fields = ("triggered_at", "acknowledged_at", "resolved_at")

    actions = ["resolve_selected"]

    @admin.action(description="✅ Résoudre les alertes sélectionnées")
    def resolve_selected(self, request, queryset):
        from django.utils import timezone
        updated = queryset.exclude(status="resolved").update(
            status="resolved", resolved_at=timezone.now()
        )
        self.message_user(request, f"{updated} alerte(s) résolue(s).")

    @admin.display(description="Sévérité", ordering="severity")
    def severity_badge(self, obj):
        colors = {"low": "#8b949e", "medium": "#e3b341", "high": "#f0883e", "critical": "#f85149"}
        c = colors.get(obj.severity, "#8b949e")
        return format_html('<span style="color:{};font-weight:bold">{}</span>', c, obj.get_severity_display())

    @admin.display(description="Statut", ordering="status")
    def status_badge(self, obj):
        colors = {"active": "#f85149", "acknowledged": "#e3b341", "resolved": "#3fb950"}
        c = colors.get(obj.status, "#8b949e")
        return format_html('<span style="color:{}">{}</span>', c, obj.get_status_display())
