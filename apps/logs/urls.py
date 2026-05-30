from django.urls import path
from . import views
from .exports import LogExportCSVView, LogExportJSONView

app_name = "logs"

urlpatterns = [
    path("",                    views.LogListView.as_view(),    name="list"),
    path("<int:pk>/",           views.LogDetailView.as_view(),  name="detail"),
    path("export/csv/",         LogExportCSVView.as_view(),     name="export_csv"),
    path("export/json/",        LogExportJSONView.as_view(),    name="export_json"),
]
