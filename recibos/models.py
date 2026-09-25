"""Modelos de recibos (Fase 4). Diseño aprobado en
docs/MODELOS_cambio_ingresos.md, sección `SerieRecibo`/`Recibo`.

Un `Aporte` recibe su recibo en el momento en que pasa a «verificado»
(D-09, ver `Aporte.transicionar()` en `ingresos/models.py`), en la misma
transacción. El número nunca sale de `max()+1`: siempre de
`SerieRecibo.select_for_update()` + incremento, para que no queden huecos
ni duplicados aunque dos verificaciones lleguen al mismo tiempo.
"""

import uuid as uuid_lib

from django.conf import settings
from django.db import models


class SerieRecibo(models.Model):
    """Una serie de numeración por período escolar. `prefijo` normalmente
    es el nombre del período ('2026-2027'), pero queda editable por si algún
    período necesita otro."""

    periodo = models.OneToOneField(
        "core.PeriodoEscolar", on_delete=models.PROTECT, related_name="serie_recibo",
    )
    prefijo = models.CharField(max_length=20, help_text='Ej: "2026-2027".')
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "serie de recibos"
        verbose_name_plural = "series de recibos"

    def __str__(self):
        return f"{self.prefijo} (último emitido: {self.ultimo_numero})"


class Recibo(models.Model):
    """Comprobante de un `Aporte` verificado. Los montos, la tasa y la forma
    de pago NO se copian aquí: salen del `Aporte`, que ya es inmutable desde
    que se verifica (D-09). Lo que sí se congela (I-6) son los nombres, para
    que el recibo diga siempre lo mismo aunque después cambien los datos de
    origen (el representante se reactiva con otro nombre, la sección se
    renombra, etc.)."""

    aporte = models.OneToOneField(
        "ingresos.Aporte", on_delete=models.PROTECT, related_name="recibo",
    )
    serie = models.ForeignKey(SerieRecibo, on_delete=models.PROTECT, related_name="recibos")
    numero = models.PositiveIntegerField()
    numero_texto = models.CharField(max_length=40, unique=True)
    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    fecha_emision = models.DateTimeField()
    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recibos_emitidos",
    )

    # --- Copias congeladas (I-6) --------------------------------------------
    entregado_por_texto = models.CharField(max_length=150, blank=True)
    estudiante_texto = models.CharField(
        max_length=150, blank=True, help_text="Vacío para ingresos sin estudiante (D-19).",
    )
    seccion_texto = models.CharField(max_length=100, blank=True)
    concepto_texto = models.CharField(max_length=150, blank=True)
    docente_texto = models.CharField(max_length=150, blank=True)

    # --- Anulación (cascada desde Aporte.transicionar) ----------------------
    anulado = models.BooleanField(default=False)
    motivo_anulacion = models.TextField(blank=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="recibos_anulados",
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "recibo"
        verbose_name_plural = "recibos"
        constraints = [
            models.UniqueConstraint(fields=["serie", "numero"], name="recibo_numero_unico_por_serie"),
        ]
        ordering = ["-numero"]

    def __str__(self):
        return self.numero_texto
