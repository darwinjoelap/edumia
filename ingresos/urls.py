from django.urls import path

from . import views

app_name = "ingresos"

urlpatterns = [
    path("registrar/", views.aporte_registrar, name="aporte_registrar"),
    path("bandeja/", views.aporte_bandeja, name="aporte_bandeja"),
    path("<int:pk>/verificar/", views.aporte_verificar, name="aporte_verificar"),
    path("<int:pk>/observar/", views.aporte_observar, name="aporte_observar"),
    path("<int:pk>/anular/", views.aporte_anular, name="aporte_anular"),

    # Configuración: catálogos (rol administrador)
    path("configuracion/conceptos/", views.ConceptoIngresoListView.as_view(), name="concepto_lista"),
    path("configuracion/conceptos/nuevo/", views.ConceptoIngresoCreateView.as_view(), name="concepto_crear"),
    path(
        "configuracion/conceptos/<int:pk>/editar/",
        views.ConceptoIngresoUpdateView.as_view(), name="concepto_editar",
    ),
    path("configuracion/formas-pago/", views.FormaPagoListView.as_view(), name="formapago_lista"),
    path("configuracion/formas-pago/nueva/", views.FormaPagoCreateView.as_view(), name="formapago_crear"),
    path(
        "configuracion/formas-pago/<int:pk>/editar/",
        views.FormaPagoUpdateView.as_view(), name="formapago_editar",
    ),
]
