from django.urls import path
from . import views

app_name = "services"

urlpatterns = [
    path("",                  views.ServiceListView.as_view(),   name="list"),
    path("create/",           views.ServiceCreateView.as_view(), name="create"),
    path("<int:pk>/edit/",    views.ServiceEditView.as_view(),   name="edit"),
    path("<int:pk>/delete/",  views.ServiceDeleteView.as_view(), name="delete"),
    path("<int:pk>/check/",   views.ServiceCheckView.as_view(),  name="check"),
]
