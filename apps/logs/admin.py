"""
apps/logs/admin.py
─────────────────────────────────────────────────────────────────
Administration des modèles LogSource et LogEntry.
Actions bulk : marquer comme résolu, supprimer les vieux logs.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import LogEntry, LogSource


@admin.register(LogSource)
class LogSourceAdmin(admin.ModelAdmin):
    list_display  = ("name", "source_type", "hostname", "is_active", "recent_error_count_display", "created_at")
    list_filter   = ("source_type", "is_active")
    search_fields = ("name", "hostname")
    ordering      = ("name",)

    @admin.display(description="Erreurs (24h)")
    def recent_error_count_display(self, obj):
        count = obj.recent_error_count
        if count > 0:
            return format_html('<span style="color:#f85149;font-weight:bold">{}</span>', count)
        return format_html('<span style="color:#3fb950">0</span>')


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display  = ("timestamp", "level_badge", "source", "short_message", "is_resolved", "ingested_at")
    list_filter   = ("level", "is_resolved", "source", "ingested_at")
    search_fields = ("message", "logger_name", "traceback")
    ordering      = ("-timestamp",)
    date_hierarchy = "timestamp"
    readonly_fields = ("ingested_at",)

    # ── Actions en masse ──────────────────────────────────────────────
    actions = ["mark_resolved", "mark_unresolved"]

    @admin.action(description="✅ Marquer comme résolus")
    def mark_resolved(self, request, queryset):
        updated = queryset.update(is_resolved=True)
        self.message_user(request, f"{updated} log(s) marqué(s) comme résolu(s).")

    @admin.action(description="🔄 Marquer comme non résolus")
    def mark_unresolved(self, request, queryset):
        updated = queryset.update(is_resolved=False)
        self.message_user(request, f"{updated} log(s) remis en non résolu.")

    @admin.display(description="Niveau", ordering="level")
    def level_badge(self, obj):
        colors = {
            "DEBUG":    "#8b949e",
            "INFO":     "#388bfd",
            "WARNING":  "#e3b341",
            "ERROR":    "#f85149",
            "CRITICAL": "#ff6e6e",
        }
        color = colors.get(obj.level, "#8b949e")
        return format_html(
            '<span style="color:{};font-weight:bold;font-family:monospace">{}</span>',
            color, obj.level
        )

    @admin.display(description="Message")
    def short_message(self, obj):
        return obj.message[:100] + ("…" if len(obj.message) > 100 else "")
