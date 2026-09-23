from django.contrib import admin
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("salud/", core_views.salud, name="salud"),
    path("admin/", admin.site.urls),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("academico/", include("academico.urls")),
    path("", core_views.inicio, name="inicio"),
]
