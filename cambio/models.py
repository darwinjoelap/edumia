from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class TasaCambio(models.Model):
    """Tasa de cambio Bs./USD de un día y una fuente.

    D-02 revisado (2026-09-25): `valor` SÍ se puede editar aunque ya tenga
    transacciones (Aporte, y a futuro Gasto). Al guardar un cambio de valor,
    `save()` recalcula en cascada los aportes que la usan y todavía están en
    «registrado» u «observado» (para que la corrección de una tasa mal
    cargada se refleje en lo que ya se registró ese día). Los que ya están
    «verificado» o «anulado» NO se tocan: siguen protegidos por D-09 (lo
    verificado no cambia; si estaba mal, se anula y se registra de nuevo)."""

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
        """True si algún Aporte o Gasto ya quedó congelado con esta tasa."""
        if hasattr(self, "aportes") and self.aportes.exists():
            return True
        if hasattr(self, "gastos") and self.gastos.exists():
            return True
        return False

    def _transacciones_recalculables(self):
        """Transacciones que SÍ se recalculan si `valor` cambia: las que no
        están congeladas todavía (D-09 protege verificado/anulado en Aporte,
        y aprobado/anulado en Gasto)."""
        from ingresos.models import Aporte

        qs = [self.aportes.filter(estado__in=[Aporte.Estado.REGISTRADO, Aporte.Estado.OBSERVADO])]
        if hasattr(self, "gastos"):
            from gastos.models import Gasto

            qs.append(self.gastos.filter(estado=Gasto.Estado.REGISTRADO))
        return qs

    def save(self, *args, **kwargs):
        valor_cambio = self.pk and self.valor != self._valor_original
        super().save(*args, **kwargs)
        if valor_cambio:
            for conjunto in self._transacciones_recalculables():
                for transaccion in conjunto:
                    if hasattr(transaccion, "recalcular"):
                        # Gasto: el total sale de sumar los renglones (no de
                        # calcular_montos()), así que hay que recongelar cada
                        # renglón con la tasa nueva antes de resumar.
                        for renglon in transaccion.renglones.all():
                            renglon.save()
                        transaccion.recalcular()
                    else:
                        transaccion.save()  # Aporte: dispara calcular_montos() con el nuevo valor
        self._valor_original = self.valor


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
