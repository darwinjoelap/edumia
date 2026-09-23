import types

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Institucion, PeriodoEscolar, PerfilUsuario, RegistroAuditoria

User = get_user_model()


def _solo_superusuario(self, request):
    """El panel de Django (/admin/) es solo para el superusuario.

    El rol 'administrador' de Edumia (control total sobre la operación
    diaria) tiene su propio panel en /configuracion/; el admin de Django
    queda reservado para quien de verdad administra el servidor.
    """
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = types.MethodType(_solo_superusuario, admin.site)


@admin.register(Institucion)
class InstitucionAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rif", "telefono"]

    def has_add_permission(self, request):
        # Singleton: no se crean instituciones nuevas si ya existe una.
        return not Institucion.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PeriodoEscolar)
class PeriodoEscolarAdmin(admin.ModelAdmin):
    list_display = ["nombre", "fecha_inicio", "fecha_fin", "activo", "cerrado"]
    list_filter = ["activo", "cerrado"]
    search_fields = ["nombre"]


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ["fecha", "usuario", "accion", "modelo", "objeto_id"]
    list_filter = ["accion"]
    search_fields = ["modelo", "objeto_id", "descripcion"]
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    fk_name = "user"


class UserAdmin(DjangoUserAdmin):
    inlines = [PerfilUsuarioInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
