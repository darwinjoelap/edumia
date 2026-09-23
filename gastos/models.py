from django.db import models
from django.db.models import Q

# Nota: este archivo por ahora solo trae Fondo, adelantado desde la Fase 5
# porque PerfilUsuario.fondo (Fase 2) necesita apuntar a algo. El resto del
# diseño de gastos (docs/MODELOS_gastos.md: CategoriaGasto, UnidadMedida,
# Producto, Proveedor, Gasto, DetalleGasto) se construye en la Fase 5.


class Fondo(models.Model):
    nombre = models.CharField(max_length=80, unique=True, help_text="Ej: Comedor, Mantenimiento, General")
    descripcion = models.CharField(max_length=200, blank=True)
    es_general = models.BooleanField(
        default=False, help_text="Exactamente un fondo debe tener esto en True: el Fondo General."
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "fondo"
        verbose_name_plural = "fondos"
        constraints = [
            models.UniqueConstraint(
                fields=["es_general"], condition=Q(es_general=True), name="un_solo_fondo_general",
            ),
        ]
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
