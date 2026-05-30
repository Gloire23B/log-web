"""
LogMonitor Dashboard — Configuration des URLs racines
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Administration Django
    path("admin/", admin.site.urls),
    # Authentification
    path("auth/", include("apps.accounts.urls")),
    # Dashboard principal
    path("dashboard/", include("apps.dashboard.urls")),
    # Logs
    path("logs/", include("apps.logs.urls")),
    # Alertes
    path("alerts/", include("apps.alerts.urls")),
    # Serveurs
    path("servers/", include("apps.servers.urls")),
    # Services
    path("services/", include("apps.services.urls")),
    # API REST v1 — ingestion de logs
    path("api/v1/", include("apps.logs.api_urls")),
    # Redirection racine vers le dashboard
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
]

# Médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
