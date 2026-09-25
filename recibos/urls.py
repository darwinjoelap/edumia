from django.urls import path

from . import views

app_name = "recibos"

urlpatterns = [
    path("<int:pk>/", views.recibo_detalle, name="recibo_detalle"),
    path("verificar/<uuid:uuid>/", views.recibo_publico, name="recibo_publico"),
]
