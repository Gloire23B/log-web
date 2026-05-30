"""
LogMonitor Dashboard — Configuration des URLs racines
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Administration Django
    path("admin/", admin.site.urls),
    # Authentification
    path("auth/", include("apps.accounts.urls", namespace="accounts")),
    # Dashboard principal
    path("dashboard/", include("apps.dashboard.urls", namespace="dashboard")),
    # Logs
    path("logs/", include("apps.logs.urls", namespace="logs")),
    # Alertes
    path("alerts/", include("apps.alerts.urls", namespace="alerts")),
    # Serveurs
    path("servers/", include("apps.servers.urls", namespace="servers")),
    # API REST v1 — ingestion de logs
    path("api/v1/", include("apps.logs.api_urls")),
    # Services
    path("services/", include("apps.services.urls", namespace="services")),
    # Redirection racine vers le dashboard
    path("", include("apps.dashboard.urls", namespace="dashboard_root")),
]

# Médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
