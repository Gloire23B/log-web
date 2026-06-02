from django.urls import path
from . import views

app_name = "servers"

urlpatterns = [
    path("",                          views.ServerListView.as_view(),         name="list"),
    path("create/",                   views.ServerCreateView.as_view(),       name="create"),
    path("<int:pk>/edit/",            views.ServerEditView.as_view(),         name="edit"),
    path("<int:pk>/delete/",          views.ServerDeleteView.as_view(),       name="delete"),
    path("<int:pk>/check/",           views.ServerCheckView.as_view(),        name="check"),
    path("<int:pk>/agent-script/",    views.ServerAgentScriptView.as_view(),  name="agent_script"),
    path("<int:pk>/ssh-collect/",     views.ServerSSHCollectView.as_view(),   name="ssh_collect"),
]
