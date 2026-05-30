"""
apps/dashboard/urls.py — Routes du dashboard
"""
from django.urls import path
from . import views
from .sse import DashboardSSEView

app_name = "dashboard"

urlpatterns = [
    path("",                   views.DashboardView.as_view(),       name="index"),
    path("htmx/recent-logs/",  views.RecentLogsHtmxView.as_view(),  name="htmx_recent_logs"),
    path("htmx/chart/volume/", views.LogVolumeChartView.as_view(),  name="htmx_chart_volume"),
    path("stream/",            DashboardSSEView.as_view(),          name="sse_stream"),
]
