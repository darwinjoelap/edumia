from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("sin-conexion/", views.sin_conexion, name="sin_conexion"),
    path("proximamente/", views.proximamente, name="proximamente"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("configuracion/institucion/", views.InstitucionUpdateView.as_view(), name="institucion_editar"),
    path("configuracion/grados/", views.GradoListView.as_view(), name="grado_lista"),
    path("configuracion/grados/nuevo/", views.GradoCreateView.as_view(), name="grado_crear"),
    path("configuracion/grados/<int:pk>/editar/", views.GradoUpdateView.as_view(), name="grado_editar"),
    path("configuracion/grados/<int:pk>/eliminar/", views.grado_eliminar, name="grado_eliminar"),
    path("configuracion/periodos/", views.PeriodoListView.as_view(), name="periodo_lista"),
    path("configuracion/periodos/nuevo/", views.PeriodoCreateView.as_view(), name="periodo_crear"),
    path("configuracion/periodos/<int:pk>/editar/", views.PeriodoUpdateView.as_view(), name="periodo_editar"),
    path("configuracion/periodos/<int:pk>/activar/", views.periodo_activar, name="periodo_activar"),
    path("configuracion/periodos/<int:pk>/cerrar/", views.periodo_cerrar, name="periodo_cerrar"),
    path("configuracion/periodos/<int:pk>/eliminar/", views.periodo_eliminar, name="periodo_eliminar"),
    path("configuracion/secciones/", views.SeccionListView.as_view(), name="seccion_lista"),
    path("configuracion/secciones/nueva/", views.SeccionCreateView.as_view(), name="seccion_crear"),
    path("configuracion/secciones/<int:pk>/editar/", views.SeccionUpdateView.as_view(), name="seccion_editar"),
    path(
        "configuracion/secciones/<int:pk>/activar/",
        views.seccion_toggle_activa,
        name="seccion_toggle_activa",
    ),
    path("configuracion/secciones/<int:pk>/eliminar/", views.seccion_eliminar, name="seccion_eliminar"),
    path("configuracion/bitacora/", views.BitacoraListView.as_view(), name="bitacora_lista"),
    path("configuracion/usuarios/", views.UsuarioListView.as_view(), name="usuario_lista"),
    path("configuracion/usuarios/nuevo/", views.usuario_crear, name="usuario_crear"),
    path("configuracion/usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path(
        "configuracion/usuarios/<int:pk>/restablecer-clave/",
        views.usuario_restablecer_clave,
        name="usuario_restablecer_clave",
    ),
    path(
        "configuracion/usuarios/<int:pk>/activar-desactivar/",
        views.usuario_toggle_activo,
        name="usuario_toggle_activo",
    ),
]
