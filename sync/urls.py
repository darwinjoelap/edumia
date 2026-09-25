from django.urls import path

from . import views

app_name = "sync"

urlpatterns = [
    path("api/aporte/", views.api_sync_aporte, name="api_sync_aporte"),
    path("api/gasto/", views.api_sync_gasto, name="api_sync_gasto"),
]
