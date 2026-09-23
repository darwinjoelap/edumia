from django.contrib import admin

from .models import Fondo


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
