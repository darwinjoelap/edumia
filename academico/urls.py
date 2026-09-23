from django.urls import path

from . import views

app_name = "academico"

urlpatterns = [
    path(
        "secciones/<int:seccion_id>/alta-rapida/",
        views.alta_rapida_seccion,
        name="alta_rapida_seccion",
    ),
    path(
        "secciones/<int:seccion_id>/importar/",
        views.importar_estudiantes_seccion,
        name="importar_estudiantes_seccion",
    ),
    path("representantes/", views.RepresentanteListView.as_view(), name="representante_lista"),
    path("representantes/nuevo/", views.RepresentanteCreateView.as_view(), name="representante_crear"),
    path("representantes/<int:pk>/", views.representante_detalle, name="representante_detalle"),
    path(
        "representantes/<int:pk>/editar/",
        views.RepresentanteUpdateView.as_view(),
        name="representante_editar",
    ),
    path(
        "representantes/<int:pk>/activar/",
        views.representante_toggle_activo,
        name="representante_toggle_activo",
    ),
    path(
        "representantes/<int:pk>/vinculos/<int:vinculo_id>/eliminar/",
        views.vinculo_eliminar,
        name="vinculo_eliminar",
    ),
    path("estudiantes/", views.EstudianteListView.as_view(), name="estudiante_lista"),
    path("estudiantes/<int:pk>/", views.estudiante_detalle, name="estudiante_detalle"),
    path(
        "estudiantes/<int:pk>/editar/",
        views.EstudianteUpdateView.as_view(),
        name="estudiante_editar",
    ),
    path(
        "estudiantes/<int:pk>/activar/",
        views.estudiante_toggle_activo,
        name="estudiante_toggle_activo",
    ),
    path("promocion/", views.promocion_masiva, name="promocion_masiva"),
]
