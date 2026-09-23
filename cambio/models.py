from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class TasaCambio(models.Model):
    """Tasa de cambio Bs./USD de un día y una fuente. No se edita `valor` una
    vez que alguna transacción (Aporte, Gasto — Fases 3/5) la referencia; se
    corrige cargando una fila nueva, así el pasado no cambia (las
    transacciones guardan su propio `tasa_aplicada`). Por ahora no hay
    transacciones que la referencien, así que esa regla no se puede aplicar
    todavía en código: queda para cuando exista MontoBimonedaMixin."""

    class Fuente(models.TextChoices):
        BCV = "bcv", "BCV"
        PARALELO = "paralelo", "Paralelo"
        CONSEJO = "consejo", "Consejo"
        MANUAL = "manual", "Manual"

    fecha = models.DateField()
    valor = models.DecimalField(max_digits=18, decimal_places=4, help_text="Bs. por 1 USD.")
    fuente = models.CharField(max_length=10, choices=Fuente.choices)
    cargada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tasas_cargadas"
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "tasa de cambio"
        verbose_name_plural = "tasas de cambio"
        constraints = [
            models.UniqueConstraint(fields=["fecha", "fuente"], name="tasa_unica_por_fecha_y_fuente"),
            models.CheckConstraint(check=models.Q(valor__gt=0), name="tasa_valor_positivo"),
        ]
        indexes = [
            models.Index(fields=["fuente", "-fecha"]),
        ]
        ordering = ["-fecha", "fuente"]

    def __str__(self):
        return f"{self.fecha} · {self.get_fuente_display()}: {self.valor}"
