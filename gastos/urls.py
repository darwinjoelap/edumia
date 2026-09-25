from django.urls import path

from . import views

app_name = "gastos"

urlpatterns = [
    path("registrar/", views.gasto_registrar, name="gasto_registrar"),
    path("renglon-nuevo/", views.gasto_renglon_nuevo, name="gasto_renglon_nuevo"),
    path("bandeja/", views.gasto_bandeja, name="gasto_bandeja"),
    path("lista/", views.GastoListView.as_view(), name="gasto_lista"),
    path("<int:pk>/", views.gasto_detalle, name="gasto_detalle"),
    path("<int:pk>/editar/", views.gasto_editar, name="gasto_editar"),
    path("<int:pk>/aprobar/", views.gasto_aprobar, name="gasto_aprobar"),
    path("<int:pk>/anular/", views.gasto_anular, name="gasto_anular"),

    # Configuración: catálogos (rol administrador)
    path("configuracion/categorias/", views.CategoriaGastoListView.as_view(), name="categoria_lista"),
    path("configuracion/categorias/nueva/", views.CategoriaGastoCreateView.as_view(), name="categoria_crear"),
    path(
        "configuracion/categorias/<int:pk>/editar/",
        views.CategoriaGastoUpdateView.as_view(), name="categoria_editar",
    ),
    path("configuracion/categorias/<int:pk>/eliminar/", views.categoria_eliminar, name="categoria_eliminar"),
    path("configuracion/unidades/", views.UnidadMedidaListView.as_view(), name="unidad_lista"),
    path("configuracion/unidades/nueva/", views.UnidadMedidaCreateView.as_view(), name="unidad_crear"),
    path(
        "configuracion/unidades/<int:pk>/editar/",
        views.UnidadMedidaUpdateView.as_view(), name="unidad_editar",
    ),
    path("configuracion/unidades/<int:pk>/eliminar/", views.unidad_eliminar, name="unidad_eliminar"),
    path("configuracion/productos/", views.ProductoListView.as_view(), name="producto_lista"),
    path("configuracion/productos/nuevo/", views.ProductoCreateView.as_view(), name="producto_crear"),
    path(
        "configuracion/productos/<int:pk>/editar/",
        views.ProductoUpdateView.as_view(), name="producto_editar",
    ),
    path("configuracion/productos/<int:pk>/eliminar/", views.producto_eliminar, name="producto_eliminar"),
    path("configuracion/proveedores/", views.ProveedorListView.as_view(), name="proveedor_lista"),
    path("configuracion/proveedores/nuevo/", views.ProveedorCreateView.as_view(), name="proveedor_crear"),
    path(
        "configuracion/proveedores/<int:pk>/editar/",
        views.ProveedorUpdateView.as_view(), name="proveedor_editar",
    ),
    path("configuracion/proveedores/<int:pk>/eliminar/", views.proveedor_eliminar, name="proveedor_eliminar"),
    path("configuracion/fondos/", views.FondoListView.as_view(), name="fondo_lista"),
    path("configuracion/fondos/nuevo/", views.FondoCreateView.as_view(), name="fondo_crear"),
    path("configuracion/fondos/<int:pk>/editar/", views.FondoUpdateView.as_view(), name="fondo_editar"),

    # Transferencias entre fondos (D-36)
    path("transferencias/", views.TransferenciaFondoListView.as_view(), name="transferencia_lista"),
    path("transferencias/nueva/", views.transferencia_registrar, name="transferencia_registrar"),
    path("transferencias/<int:pk>/anular/", views.transferencia_anular, name="transferencia_anular"),
]
