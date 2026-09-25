from django.contrib import admin

from .models import Aporte, Banco, ConceptoIngreso, FormaPago, MontoConcepto


@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "activo"]
    list_filter = ["activo"]
    search_fields = ["codigo", "nombre"]
    ordering = ["nombre"]


@admin.register(FormaPago)
class FormaPagoAdmin(admin.ModelAdmin):
    list_display = [
        "nombre", "moneda_fija", "requiere_banco_destino", "requiere_banco_origen",
        "requiere_referencia", "requiere_telefono", "requiere_cedula", "activo",
    ]
    list_filter = ["activo", "moneda_fija"]
    search_fields = ["nombre"]


@admin.register(ConceptoIngreso)
class ConceptoIngresoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "periodicidad", "monto_sugerido", "moneda_sugerida", "fondo", "activo"]
    list_filter = ["periodicidad", "activo", "fondo"]
    search_fields = ["nombre"]


@admin.register(MontoConcepto)
class MontoConceptoAdmin(admin.ModelAdmin):
    list_display = ["concepto", "grado", "periodo", "monto", "moneda"]
    list_filter = ["periodo", "grado", "concepto"]


@admin.register(Aporte)
class AporteAdmin(admin.ModelAdmin):
    list_display = [
        "id", "concepto", "inscripcion", "monto", "moneda", "estado",
        "fecha_pago", "registrado_por", "periodo",
    ]
    list_filter = ["estado", "periodo", "concepto", "forma_pago"]
    search_fields = [
        "cedula_titular", "telefono_emisor", "referencia",
        "entregado_por_nombre", "nombre_titular", "concepto_libre",
    ]
    date_hierarchy = "fecha_pago"
    readonly_fields = [
        "tasa_aplicada", "monto_ves", "monto_usd", "creado_en", "actualizado_en",
        "fecha_registro", "fecha_verificacion", "fecha_anulacion",
    ]

    def has_delete_permission(self, request, obj=None):
        # D-09: nada se borra; la única salida es anular.
        return False
