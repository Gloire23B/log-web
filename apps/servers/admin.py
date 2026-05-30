"""apps/servers/admin.py"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Server


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display  = ("name", "ip_address", "environment", "status_badge",
                     "cpu_display", "memory_display", "disk_display", "last_seen")
    list_filter   = ("environment", "status", "is_active")
    search_fields = ("name", "hostname", "ip_address")
    ordering      = ("environment", "name")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Statut", ordering="status")
    def status_badge(self, obj):
        colors = {
            "online": "#3fb950", "warning": "#e3b341",
            "critical": "#f85149", "offline": "#8b949e", "unknown": "#484f58"
        }
        c = colors.get(obj.status, "#8b949e")
        return format_html('<span style="color:{};font-weight:bold">● {}</span>', c, obj.get_status_display())

    @admin.display(description="CPU")
    def cpu_display(self, obj):
        if obj.cpu_percent is None: return "—"
        c = "#f85149" if obj.cpu_percent >= 90 else "#e3b341" if obj.cpu_percent >= 75 else "#3fb950"
        return format_html('<span style="color:{}">{:.1f}%</span>', c, obj.cpu_percent)

    @admin.display(description="RAM")
    def memory_display(self, obj):
        if obj.memory_percent is None: return "—"
        c = "#f85149" if obj.memory_percent >= 90 else "#e3b341" if obj.memory_percent >= 80 else "#388bfd"
        return format_html('<span style="color:{}">{:.1f}%</span>', c, obj.memory_percent)

    @admin.display(description="Disque")
    def disk_display(self, obj):
        if obj.disk_percent is None: return "—"
        c = "#f85149" if obj.disk_percent >= 90 else "#e3b341" if obj.disk_percent >= 75 else "#8b55da"
        return format_html('<span style="color:{}">{:.1f}%</span>', c, obj.disk_percent)
