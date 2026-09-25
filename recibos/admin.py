from django.contrib import admin

from .models import Recibo, SerieRecibo


@admin.register(SerieRecibo)
class SerieReciboAdmin(admin.ModelAdmin):
    list_display = ("prefijo", "periodo", "ultimo_numero")
    readonly_fields = ("periodo", "prefijo", "ultimo_numero")

    def has_add_permission(self, request):
        # Se crea sola (get_or_create) al emitir el primer recibo del período.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Recibo)
class ReciboAdmin(admin.ModelAdmin):
    list_display = ("numero_texto", "concepto_texto", "estudiante_texto", "fecha_emision", "anulado")
    list_filter = ("anulado", "serie")
    search_fields = ("numero_texto", "estudiante_texto", "entregado_por_texto", "uuid")
    readonly_fields = [f.name for f in Recibo._meta.fields]

    def has_add_permission(self, request):
        # Solo se crea desde Aporte.transicionar() al verificar (D-09).
        return False

    def has_delete_permission(self, request, obj=None):
        return False
