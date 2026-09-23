from django.contrib import admin

from .models import (
    EstudianteRepresentante,
    Estudiante,
    Grado,
    Inscripcion,
    Representante,
    Seccion,
)


@admin.register(Grado)
class GradoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "nivel", "orden"]
    list_filter = ["nivel"]
    search_fields = ["nombre"]  # requerido para autocomplete_fields en SeccionAdmin
    ordering = ["orden"]


@admin.register(Seccion)
class SeccionAdmin(admin.ModelAdmin):
    list_display = ["grado", "nombre", "periodo", "docente_responsable", "activa"]
    list_filter = ["periodo", "grado__nivel", "activa"]
    search_fields = ["nombre", "grado__nombre"]
    autocomplete_fields = ["grado", "periodo", "docente_responsable"]


class EstudianteRepresentanteInline(admin.TabularInline):
    model = EstudianteRepresentante
    extra = 1
    autocomplete_fields = ["representante"]


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 0
    autocomplete_fields = ["seccion", "periodo"]


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ["apellidos", "nombres", "cedula_escolar", "activo"]
    list_filter = ["activo", "sexo"]
    search_fields = ["nombres", "apellidos", "cedula_escolar"]
    inlines = [InscripcionInline, EstudianteRepresentanteInline]


@admin.register(Representante)
class RepresentanteAdmin(admin.ModelAdmin):
    list_display = ["apellidos", "nombres", "cedula", "telefono", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombres", "apellidos", "cedula", "telefono"]


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ["estudiante", "seccion", "periodo", "estado", "fecha"]
    list_filter = ["periodo", "estado", "seccion"]
    search_fields = ["estudiante__nombres", "estudiante__apellidos"]
    autocomplete_fields = ["estudiante", "seccion", "periodo"]
