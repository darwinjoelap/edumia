from django.contrib import admin

from .models import CategoriaGasto, DetalleGasto, Fondo, Gasto, Producto, Proveedor, UnidadMedida


@admin.register(Fondo)
class FondoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "es_general", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre"]

    def has_delete_permission(self, request, obj=None):
        # El Fondo General no se borra; para el resto, se desactiva (D-09).
        if obj is not None and obj.es_general:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "abreviatura"]
    search_fields = ["nombre", "abreviatura"]


@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "fondo", "activo"]
    list_filter = ["activo", "fondo"]
    search_fields = ["nombre"]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "categoria", "unidad_default", "activo"]
    list_filter = ["activo", "categoria"]
    search_fields = ["nombre", "nombre_normalizado"]


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rif", "telefono", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre", "rif"]


class DetalleGastoInline(admin.TabularInline):
    model = DetalleGasto
    extra = 0
    readonly_fields = ["producto", "descripcion", "cantidad", "unidad", "precio_unitario", "subtotal", "subtotal_ves", "subtotal_usd"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ["id", "fondo", "proveedor", "monto", "moneda", "estado", "fecha", "registrado_por"]
    list_filter = ["estado", "periodo", "fondo", "tipo_documento"]
    search_fields = ["numero_documento", "observacion"]
    date_hierarchy = "fecha"
    readonly_fields = [
        "tasa_aplicada", "monto_ves", "monto_usd", "creado_en", "actualizado_en",
        "fecha_registro", "fecha_aprobacion", "fecha_anulacion",
    ]
    inlines = [DetalleGastoInline]

    def has_delete_permission(self, request, obj=None):
        # D-09: nada se borra; la única salida es anular.
        return False
