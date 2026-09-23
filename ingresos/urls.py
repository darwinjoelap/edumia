from django.urls import path

from . import views

app_name = "ingresos"

urlpatterns = [
    path("registrar/", views.aporte_registrar, name="aporte_registrar"),
    path("bandeja/", views.aporte_bandeja, name="aporte_bandeja"),
    path("<int:pk>/verificar/", views.aporte_verificar, name="aporte_verificar"),
    path("<int:pk>/observar/", views.aporte_observar, name="aporte_observar"),
    path("<int:pk>/anular/", views.aporte_anular, name="aporte_anular"),
]
