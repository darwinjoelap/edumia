from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ingresos/", views.ingresos_estudiantes, name="ingresos_estudiantes"),
    path("gastos/", views.gastos_categorias, name="gastos_categorias"),
    path("balance/", views.balance, name="balance"),
    path("gastos/relacion-pdf/", views.relacion_gastos_pdf, name="relacion_gastos_pdf"),
    path("estudiante/", views.estudiante_cuenta, name="estudiante_cuenta"),
]
