from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
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
    path("configuracion/secciones/", views.SeccionListView.as_view(), name="seccion_lista"),
    path("configuracion/secciones/nueva/", views.SeccionCreateView.as_view(), name="seccion_crear"),
    path("configuracion/secciones/<int:pk>/editar/", views.SeccionUpdateView.as_view(), name="seccion_editar"),
    path(
        "configuracion/secciones/<int:pk>/activar/",
        views.seccion_toggle_activa,
        name="seccion_toggle_activa",
    ),
]
