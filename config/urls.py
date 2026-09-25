from django.contrib import admin
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("salud/", core_views.salud, name="salud"),
    # Servido en la raíz (no bajo /static/) para que el scope por defecto
    # del service worker cubra todo el sitio.
    path("sw.js", core_views.service_worker, name="sw_js"),
    path("admin/", admin.site.urls),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("academico/", include("academico.urls")),
    path("ingresos/", include("ingresos.urls")),
    path("cambio/", include("cambio.urls")),
    path("", include("core.urls")),
    path("", core_views.inicio, name="inicio"),
]
