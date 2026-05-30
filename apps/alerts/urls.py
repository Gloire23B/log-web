"""
apps/alerts/urls.py — Routes du module alertes
"""
from django.urls import path
from . import views

app_name = "alerts"

urlpatterns = [
    path("",                      views.AlertListView.as_view(),        name="list"),
    path("<int:pk>/acknowledge/", views.AlertAcknowledgeView.as_view(), name="acknowledge"),
    path("<int:pk>/resolve/",     views.AlertResolveView.as_view(),     name="resolve"),
    path("htmx/stats/",          views.AlertStatsHtmxView.as_view(),   name="htmx_stats"),
]
