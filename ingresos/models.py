"""Modelos de ingresos (Fase 3). Diseño aprobado en docs/MODELOS_cambio_ingresos.md.

`SerieRecibo` y `Recibo` viven en la app `recibos` (Fase 4). `Aporte` no la
importa a nivel de módulo (evitaría un ciclo: `recibos.models.Recibo`
referencia `ingresos.Aporte`) — `transicionar()` importa `recibos.services`
de forma diferida, solo cuando hace falta emitir o anular un recibo.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from simple_history.models import HistoricalRecords

from academico.models import Inscripcion
from cambio.models import MontoBimonedaMixin
from core.utils import normalizar_cedula, normalizar_telefono
from gastos.models import Fondo


class Banco(models.Model):
    """Catálogo de bancos venezolanos, usado en pago móvil/transferencia."""

    nombre = models.CharField(max_length=80)
    codigo = models.CharField(max_length=4, unique=True, help_text="Código SUDEBAN, ej. 0102.")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "banco"
        verbose_name_plural = "bancos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"


class FormaPago(models.Model):
    """Cada forma de pago declara, con banderas, qué campos exige `Aporte`
    (ver `Aporte.clean()`). Editable desde el admin; no hay CRUD propio
    todavía porque cambia poco (se carga una vez con `seed_datos_iniciales`)."""

    nombre = models.CharField(max_length=50, unique=True)
    moneda_fija = models.CharField(
        max_length=3, choices=MontoBimonedaMixin.Moneda.choices, null=True, blank=True,
        help_text="Vacío = admite Bs. o USD. Ej: 'Divisa efectivo' y 'Zelle' solo admiten USD.",
    )
    requiere_banco_destino = models.BooleanField(default=False)
    requiere_banco_origen = models.BooleanField(default=False)
    requiere_referencia = models.BooleanField(default=False)
    requiere_telefono = models.BooleanField(default=False)
    requiere_cedula = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "forma de pago"
        verbose_name_plural = "formas de pago"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ConceptoIngreso(models.Model):
    class Periodicidad(models.TextChoices):
        UNICO = "unico", "Único"
        MENSUAL = "mensual", "Mensual"

    nombre = models.CharField(max_length=100, unique=True)
    periodicidad = models.CharField(
        max_length=10, choices=Periodicidad.choices, default=Periodicidad.UNICO,
    )
    monto_sugerido = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="Valor por defecto cuando no hay un monto específico para el grado/período en «Montos por concepto».",
    )
    moneda_sugerida = models.CharField(
        max_length=3, choices=MontoBimonedaMixin.Moneda.choices, null=True, blank=True,
    )
    fondo = models.ForeignKey(
        Fondo, null=True, blank=True, on_delete=models.PROTECT, related_name="conceptos_ingreso",
        help_text="Fondo al que entra el dinero. Vacío = Fondo General.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "concepto de ingreso"
        verbose_name_plural = "conceptos de ingreso"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.monto_sugerido is not None and not self.moneda_sugerida:
            raise ValidationError({"moneda_sugerida": "Si defines un monto sugerido, indica su moneda."})


class MontoConcepto(models.Model):
    """Monto esperado de un concepto para un grado y período concretos
    (D-07): «la inscripción cuesta distinto en 1er grado que en 5to año»."""

    concepto = models.ForeignKey(ConceptoIngreso, on_delete=models.PROTECT, related_name="montos")
    grado = models.ForeignKey("academico.Grado", on_delete=models.PROTECT, related_name="montos_concepto")
    periodo = models.ForeignKey("core.PeriodoEscolar", on_delete=models.PROTECT, related_name="montos_concepto")
    monto = models.DecimalField(max_digits=18, decimal_places=4)
    moneda = models.CharField(max_length=3, choices=MontoBimonedaMixin.Moneda.choices)

    class Meta:
        verbose_name = "monto por concepto"
        verbose_name_plural = "montos por concepto"
        constraints = [
            models.UniqueConstraint(
                fields=["concepto", "grado", "periodo"], name="monto_unico_por_concepto_grado_periodo",
            ),
        ]
        ordering = ["periodo", "concepto", "grado__orden"]

    def __str__(self):
        return f"{self.concepto} · {self.grado} · {self.periodo}: {self.monto} {self.moneda}"


def monto_esperado(concepto, inscripcion):
    """(monto, moneda) esperado de `concepto` para el grado/período de
    `inscripcion`, o (None, None) si no hay nada configurado. Sin resultado,
    no se valida desviación ni se puede calcular morosidad para ese aporte
    (queda documentado así, no es un error).

    Resolución (D-07): 1) `MontoConcepto` del grado y período de la
    inscripción; 2) si no existe, `concepto.monto_sugerido`; 3) si tampoco, None.
    """
    if inscripcion is not None:
        fila = MontoConcepto.objects.filter(
            concepto=concepto, grado=inscripcion.seccion.grado, periodo=inscripcion.periodo,
        ).first()
        if fila:
            return fila.monto, fila.moneda
    if concepto.monto_sugerido is not None and concepto.moneda_sugerida:
        return concepto.monto_sugerido, concepto.moneda_sugerida
    return None, None


class Aporte(MontoBimonedaMixin, models.Model):
    """Un ingreso individual. Con `inscripcion` cuando corresponde a un
    estudiante; sin ella para ingresos generales de la institución (rifas,
    donaciones — D-19). Inmutable en monto/fecha/moneda/estudiante una vez
    `verificado` (D-09): de ahí solo se puede anular."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        REGISTRADO = "registrado", "Registrado"
        OBSERVADO = "observado", "Observado"
        VERIFICADO = "verificado", "Verificado"
        ANULADO = "anulado", "Anulado"

    # --- Identidad ---------------------------------------------------------
    uuid_cliente = models.UUIDField(
        null=True, blank=True, unique=True,
        help_text="Idempotencia de la cola offline (Fase 7). Vacío en los aportes hechos en línea.",
    )
    inscripcion = models.ForeignKey(
        Inscripcion, null=True, blank=True, on_delete=models.PROTECT, related_name="aportes",
        help_text="Vacío para ingresos sin estudiante (rifas, donaciones — D-19).",
    )
    concepto = models.ForeignKey(
        ConceptoIngreso, null=True, blank=True, on_delete=models.PROTECT, related_name="aportes",
        help_text="Vacío si es un ingreso no planificado (usa «concepto libre» en su lugar).",
    )
    concepto_libre = models.CharField(
        max_length=150, blank=True,
        help_text="Nombre escrito en el momento, para un ingreso no planificado que no está en el catálogo "
        "(no queda guardado como concepto reutilizable; el ingreso entra siempre al Fondo General).",
    )
    periodo = models.ForeignKey(
        "core.PeriodoEscolar", on_delete=models.PROTECT, related_name="aportes",
        help_text="Denormalizado: de inscripcion.periodo si hay inscripción, o el período activo al registrar.",
    )
    fondo = models.ForeignKey(
        Fondo, on_delete=models.PROTECT, related_name="aportes",
        help_text="Copiado de concepto.fondo al registrar (o el Fondo General si el concepto no tiene uno).",
    )

    # --- Cobertura -----------------------------------------------------------
    mes_cubierto = models.DateField(
        null=True, blank=True, verbose_name="período que cubre",
        help_text="Día 1 del mes que cubre este aporte. Obligatorio si el concepto es mensual.",
    )

    # --- Dinero (heredado de MontoBimonedaMixin: monto, moneda, tasa_aplicada,
    # monto_ves, monto_usd) más la tasa congelada -----------------------------
    tasa = models.ForeignKey(
        "cambio.TasaCambio", on_delete=models.PROTECT, related_name="aportes",
    )

    # --- Pago ------------------------------------------------------------
    forma_pago = models.ForeignKey(FormaPago, on_delete=models.PROTECT, related_name="aportes")
    fecha_pago = models.DateField()
    banco_destino = models.ForeignKey(
        Banco, null=True, blank=True, on_delete=models.PROTECT, related_name="aportes_como_destino",
    )
    banco_origen = models.ForeignKey(
        Banco, null=True, blank=True, on_delete=models.PROTECT, related_name="aportes_como_origen",
    )
    referencia = models.CharField(max_length=40, blank=True)
    telefono_emisor = models.CharField(max_length=11, blank=True)
    cedula_titular = models.CharField(max_length=20, blank=True)
    nombre_titular = models.CharField(max_length=150, blank=True)
    nota_pago = models.TextField(blank=True)

    # --- Entrega -----------------------------------------------------------
    entregado_por = models.ForeignKey(
        "academico.Representante", null=True, blank=True, on_delete=models.PROTECT,
        related_name="aportes_entregados",
    )
    entregado_por_nombre = models.CharField(
        max_length=150, blank=True, help_text="Si quien entrega no es un representante registrado.",
    )

    # --- Flujo ---------------------------------------------------------------
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.REGISTRADO)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="aportes_registrados",
    )
    fecha_registro = models.DateTimeField(null=True, blank=True)
    verificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="aportes_verificados",
    )
    fecha_verificacion = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(blank=True)
    motivo_anulacion = models.TextField(blank=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="aportes_anulados",
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)

    # --- Control -------------------------------------------------------------
    desviacion_confirmada = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "aporte"
        verbose_name_plural = "aportes"
        constraints = [
            models.UniqueConstraint(
                fields=["banco_destino", "referencia", "fecha_pago"],
                condition=~Q(referencia=""),
                name="aporte_referencia_unica_por_banco_y_fecha",
            ),
            models.CheckConstraint(check=Q(monto__gt=0), name="aporte_monto_positivo"),
        ]
        indexes = [
            models.Index(fields=["periodo", "estado"]),
            models.Index(fields=["inscripcion", "fecha_pago"]),
            models.Index(fields=["registrado_por", "estado"]),
            models.Index(fields=["cedula_titular"]),
            models.Index(fields=["telefono_emisor"]),
            models.Index(fields=["referencia"]),
        ]
        ordering = ["-creado_en"]

    def __str__(self):
        quien = self.entregado_por or self.entregado_por_nombre or "—"
        concepto = self.concepto or self.concepto_libre or "—"
        return f"{concepto} · {quien} · {self.monto} {self.moneda} ({self.get_estado_display()})"

    # --- Validación (docs/MODELOS_cambio_ingresos.md, sección Aporte) --------

    def clean(self):
        errores = {}

        if self.concepto_id and self.concepto_libre:
            errores["concepto_libre"] = (
                "No se puede elegir un concepto del catálogo y además escribir uno libre: usa solo uno."
            )
        elif not self.concepto_id and not self.concepto_libre:
            errores["concepto"] = "Elige un concepto del catálogo o escribe uno para este ingreso no planificado."

        if self.forma_pago_id:
            fp = self.forma_pago
            if fp.moneda_fija and self.moneda and self.moneda != fp.moneda_fija:
                errores["moneda"] = f"La forma de pago «{fp}» exige moneda {fp.moneda_fija}."
            if fp.requiere_banco_destino and not self.banco_destino_id:
                errores["banco_destino"] = "La forma de pago exige banco de destino."
            if fp.requiere_banco_origen and not self.banco_origen_id:
                errores["banco_origen"] = "La forma de pago exige banco de origen."
            if fp.requiere_referencia and not self.referencia:
                errores["referencia"] = "La forma de pago exige número de referencia."
            if fp.requiere_telefono and not self.telefono_emisor:
                errores["telefono_emisor"] = "La forma de pago exige teléfono del emisor."
            if fp.requiere_cedula and not self.cedula_titular:
                errores["cedula_titular"] = "La forma de pago exige cédula del titular."

        if not self.entregado_por_id and not self.entregado_por_nombre:
            errores["entregado_por_nombre"] = "Indica quién entrega el aporte (representante o un nombre)."

        if self.periodo_id and self.fecha_pago:
            periodo = self.periodo
            if not (periodo.fecha_inicio <= self.fecha_pago <= periodo.fecha_fin):
                errores["fecha_pago"] = "La fecha de pago debe estar dentro del período escolar."
            if periodo.cerrado:
                errores.setdefault("fecha_pago", "No se pueden registrar aportes en un período cerrado.")

        if self.monto is not None and self.monto <= 0:
            errores["monto"] = "El monto debe ser mayor que cero."

        if self.inscripcion_id and self.inscripcion.estado != Inscripcion.Estado.ACTIVO:
            errores["inscripcion"] = "El estudiante no tiene una inscripción activa en este período."

        if (
            self.concepto_id
            and self.concepto.periodicidad == ConceptoIngreso.Periodicidad.MENSUAL
            and not self.mes_cubierto
        ):
            errores["mes_cubierto"] = "Este concepto es mensual: indica qué mes cubre el aporte."

        if (
            self.concepto_id and self.monto is not None and self.moneda
            and self.tasa_id and not self.desviacion_confirmada
        ):
            esperado_monto, esperado_moneda = monto_esperado(self.concepto, self.inscripcion)
            if esperado_monto:
                # El esperado está en la moneda de MontoConcepto/monto_sugerido (I-2):
                # se compara convirtiendo el monto del aporte a esa misma moneda,
                # no comparando solo cuando ambas monedas ya coinciden.
                from cambio.services import convertir

                monto_ves_tmp, monto_usd_tmp = convertir(self.monto, self.moneda, self.tasa.valor)
                monto_comparar = monto_ves_tmp if esperado_moneda == "VES" else monto_usd_tmp
                desviacion_pct = abs(monto_comparar - esperado_monto) / esperado_monto * 100
                if desviacion_pct > settings.UMBRAL_DESVIACION_MONTO:
                    errores["monto"] = (
                        f"El monto se desvía más de {settings.UMBRAL_DESVIACION_MONTO}% del "
                        f"esperado ({esperado_monto} {esperado_moneda}). Confirma la desviación para continuar."
                    )

        if errores:
            raise ValidationError(errores)

    def _autocompletar_periodo_y_fondo(self):
        """Rellena `periodo` y `fondo` cuando no vienen dados. Se llama tanto
        desde `full_clean()` (para que la validación ya los vea resueltos,
        antes de que Django exija que no sean nulos) como desde `save()`
        (por si se guarda sin pasar por `full_clean()`, ej. en el admin)."""
        if not self.periodo_id:
            if self.inscripcion_id:
                self.periodo = self.inscripcion.periodo
            else:
                from core.models import PeriodoEscolar

                self.periodo = PeriodoEscolar.objects.filter(activo=True).first()

        if not self.fondo_id:
            if self.concepto_id and self.concepto.fondo_id:
                self.fondo = self.concepto.fondo
            else:
                self.fondo = Fondo.objects.filter(es_general=True).first()

    def full_clean(self, *args, **kwargs):
        # Se resuelve antes de que clean_fields() (parte de full_clean())
        # exija que periodo/fondo no sean nulos.
        self._autocompletar_periodo_y_fondo()
        return super().full_clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.cedula_titular = normalizar_cedula(self.cedula_titular) or ""
        self.telefono_emisor = normalizar_telefono(self.telefono_emisor)
        self.referencia = self.referencia.strip().upper()

        self._autocompletar_periodo_y_fondo()

        # D-09: lo verificado o anulado ya no se recalcula.
        if self.tasa_id and self.estado not in (self.Estado.VERIFICADO, self.Estado.ANULADO):
            self.calcular_montos()

        super().save(*args, **kwargs)

    # --- Máquina de estados (docs/MODELOS_cambio_ingresos.md) ----------------

    _TRANSICIONES = {
        Estado.BORRADOR: {Estado.REGISTRADO},
        Estado.REGISTRADO: {Estado.VERIFICADO, Estado.OBSERVADO, Estado.ANULADO},
        Estado.OBSERVADO: {Estado.REGISTRADO, Estado.ANULADO},
        Estado.VERIFICADO: {Estado.ANULADO},
    }

    def transicionar(self, nuevo_estado, usuario, motivo=None):
        """Único método que cambia `estado`. Ninguna vista debe hacer
        `aporte.estado = ...` directamente: así queda un solo lugar que
        conoce las transiciones válidas y sus efectos secundarios.

        Pasar a «verificado» emite el recibo (Fase 4) en la misma
        transacción (D-09); pasar a «anulado» anula el recibo si ya existía
        uno. Ninguna de las dos cosas puede quedar a medias."""
        permitidas = self._TRANSICIONES.get(self.estado, set())
        if nuevo_estado not in permitidas:
            raise ValidationError(
                f"No se puede pasar de «{self.get_estado_display()}» a «{self.Estado(nuevo_estado).label}»."
            )

        ahora = timezone.now()

        with transaction.atomic():
            if nuevo_estado == self.Estado.REGISTRADO:
                if self.fecha_registro is None:
                    self.fecha_registro = ahora
                self.full_clean()

            elif nuevo_estado == self.Estado.VERIFICADO:
                self.verificado_por = usuario
                self.fecha_verificacion = ahora

            elif nuevo_estado == self.Estado.OBSERVADO:
                if not motivo:
                    raise ValidationError("La observación es obligatoria para marcar un aporte como observado.")
                self.observacion = motivo

            elif nuevo_estado == self.Estado.ANULADO:
                if not motivo:
                    raise ValidationError("El motivo de anulación es obligatorio.")
                self.motivo_anulacion = motivo
                self.anulado_por = usuario
                self.fecha_anulacion = ahora

            self.estado = nuevo_estado
            self.save()

            if nuevo_estado == self.Estado.VERIFICADO:
                from recibos.services import emitir_recibo

                emitir_recibo(self, usuario)

            elif nuevo_estado == self.Estado.ANULADO:
                from recibos.services import anular_recibo

                anular_recibo(self, usuario, motivo)
