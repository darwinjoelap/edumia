from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords


class TasaCambio(models.Model):
    """Tasa de cambio Bs./USD de un día y una fuente. No se edita `valor` una
    vez que alguna transacción (Aporte desde la Fase 3, Gasto desde la
    Fase 5) la referencia; se corrige cargando una fila nueva, así el pasado
    no cambia (las transacciones guardan su propio `tasa_aplicada`)."""

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._valor_original = self.valor

    def __str__(self):
        return f"{self.fecha} · {self.get_fuente_display()}: {self.valor}"

    def tiene_transacciones(self):
        """True si algún Aporte (Fase 3) o Gasto (Fase 5, cuando exista) ya
        quedó congelado con esta tasa. `getattr` porque Gasto todavía no
        existe y no rompe cuando llegue si el related_name es otro."""
        if hasattr(self, "aportes") and self.aportes.exists():
            return True
        if hasattr(self, "gastos") and self.gastos.exists():
            return True
        return False

    def clean(self):
        if self.pk and self.valor != self._valor_original and self.tiene_transacciones():
            raise ValidationError(
                "No se puede editar el valor de una tasa que ya tiene aportes u otras "
                "transacciones registradas con ella: el pasado no cambia (D-02/D-09). "
                "Carga una tasa nueva en su lugar."
            )


class MontoBimonedaMixin(models.Model):
    """Abstracto: campos de dinero bimoneda que comparten `Aporte` (Fase 3) y
    `Gasto` (Fase 5). Toda la aritmética pasa por `cambio/services.py`; nada
    aquí redondea por su cuenta."""

    class Moneda(models.TextChoices):
        VES = "VES", "Bolívares"
        USD = "USD", "Dólares"

    monto = models.DecimalField(max_digits=18, decimal_places=4)
    moneda = models.CharField(max_length=3, choices=Moneda.choices)
    tasa_aplicada = models.DecimalField(max_digits=18, decimal_places=4, editable=False)
    monto_ves = models.DecimalField(max_digits=18, decimal_places=4, editable=False)
    monto_usd = models.DecimalField(max_digits=18, decimal_places=4, editable=False)

    class Meta:
        abstract = True

    def calcular_montos(self):
        """Fija `tasa_aplicada` y ambos equivalentes a partir de `self.tasa`.
        Debe llamarse antes de guardar (lo hace el `save()` del modelo
        concreto), salvo que el registro ya esté verificado/aprobado — ahí
        `save()` no debe llamarla (D-09: lo verificado no se recalcula)."""
        from .services import convertir  # import diferido: evita el ciclo models <-> services

        self.tasa_aplicada = self.tasa.valor
        self.monto_ves, self.monto_usd = convertir(self.monto, self.moneda, self.tasa.valor)
