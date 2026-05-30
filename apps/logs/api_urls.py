"""
apps/logs/api_urls.py — Routes de l'API REST d'ingestion
"""
from django.urls import path
from .api import LogIngestView, LogIngestBulkView, HealthCheckView

urlpatterns = [
    path("logs/ingest/",      LogIngestView.as_view(),     name="api_log_ingest"),
    path("logs/ingest/bulk/", LogIngestBulkView.as_view(), name="api_log_ingest_bulk"),
    path("health/",           HealthCheckView.as_view(),   name="api_health"),
]
