from django.urls import path

from . import views

app_name = "ingresos"

urlpatterns = [
    path("registrar/", views.aporte_registrar, name="aporte_registrar"),
    path("bandeja/", views.aporte_bandeja, name="aporte_bandeja"),
    path("buscar/", views.aporte_buscar, name="aporte_buscar"),
    path("lote/<int:seccion_id>/", views.aporte_registrar_lote, name="aporte_registrar_lote"),
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
    path("configuracion/montos/", views.MontoConceptoListView.as_view(), name="montoconcepto_lista"),
    path("configuracion/montos/nuevo/", views.MontoConceptoCreateView.as_view(), name="montoconcepto_crear"),
    path(
        "configuracion/montos/<int:pk>/editar/",
        views.MontoConceptoUpdateView.as_view(), name="montoconcepto_editar",
    ),
    path(
        "configuracion/montos/<int:pk>/eliminar/",
        views.montoconcepto_eliminar, name="montoconcepto_eliminar",
    ),
    path("configuracion/bancos/", views.BancoListView.as_view(), name="banco_lista"),
    path("configuracion/bancos/nuevo/", views.BancoCreateView.as_view(), name="banco_crear"),
    path("configuracion/bancos/<int:pk>/editar/", views.BancoUpdateView.as_view(), name="banco_editar"),
]
