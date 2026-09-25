"""Modelos de gastos (Fase 5). Diseño aprobado en docs/MODELOS_gastos.md.

`Fondo` viene adelantado desde la Fase 2 porque `PerfilUsuario.fondo` ya
necesitaba apuntar a algo. El resto de esta app (catálogos, `Gasto` y
`DetalleGasto`) se construye aquí.
"""

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from simple_history.models import HistoricalRecords

from cambio.models import MontoBimonedaMixin
from core.utils import normalizar_cedula


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


class UnidadMedida(models.Model):
    """Catálogo fijo (Kg, Litro, Unidad...); se carga con `seed_datos_iniciales`."""

    nombre = models.CharField(max_length=40, unique=True)
    abreviatura = models.CharField(max_length=10, unique=True)

    class Meta:
        verbose_name = "unidad de medida"
        verbose_name_plural = "unidades de medida"
        ordering = ["nombre"]

    def __str__(self):
        return self.abreviatura


class CategoriaGasto(models.Model):
    nombre = models.CharField(max_length=80)
    fondo = models.ForeignKey(
        Fondo, null=True, blank=True, on_delete=models.PROTECT, related_name="categorias_gasto",
        help_text="Vacío = aplica a cualquier fondo.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoría de gasto"
        verbose_name_plural = "categorías de gasto"
        constraints = [
            models.UniqueConstraint(fields=["nombre", "fondo"], name="categoria_unica_por_nombre_y_fondo"),
        ]
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.fondo})" if self.fondo_id else self.nombre


def _normalizar_nombre_producto(nombre: str) -> str:
    """Minúsculas, sin acentos, espacios dobles colapsados. Evita que
    "Tomate" / "tomate " / "Tomáte" cuenten como tres productos (G-5)."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", nombre) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_acentos.strip().lower())


class Producto(models.Model):
    """Catálogo que solo normaliza nombres (G-5): el precio no vive aquí,
    se congela en cada `DetalleGasto`."""

    nombre = models.CharField(max_length=120)
    nombre_normalizado = models.CharField(max_length=120, unique=True, editable=False)
    categoria = models.ForeignKey(CategoriaGasto, on_delete=models.PROTECT, related_name="productos")
    unidad_default = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name="productos")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre_normalizado = _normalizar_nombre_producto(self.nombre)
        super().save(*args, **kwargs)


class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    rif = models.CharField(max_length=20, null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"
        constraints = [
            models.UniqueConstraint(fields=["rif"], condition=~Q(rif=None), name="proveedor_rif_unico"),
        ]
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.rif = normalizar_cedula(self.rif)
        super().save(*args, **kwargs)


class Gasto(MontoBimonedaMixin, models.Model):
    """Cabecera de un gasto. `calcular_montos()` (heredado del mixin) **no**
    se usa aquí: el total se deriva sumando los renglones — ver
    `recalcular()` — porque cada renglón se convierte por su cuenta y el
    total del gasto debe cuadrar exactamente con la suma de sus partes."""

    class TipoDocumento(models.TextChoices):
        FACTURA = "factura", "Factura"
        NOTA_ENTREGA = "nota_entrega", "Nota de entrega"
        RECIBO = "recibo", "Recibo"
        SIN_SOPORTE = "sin_soporte", "Sin soporte"

    class Estado(models.TextChoices):
        REGISTRADO = "registrado", "Registrado"
        APROBADO = "aprobado", "Aprobado"
        ANULADO = "anulado", "Anulado"

    uuid_cliente = models.UUIDField(null=True, blank=True, unique=True)
    fecha = models.DateField()
    periodo = models.ForeignKey(
        "core.PeriodoEscolar", on_delete=models.PROTECT, related_name="gastos",
        help_text="Denormalizado: se deduce de la fecha al registrar.",
    )
    fondo = models.ForeignKey(Fondo, on_delete=models.PROTECT, related_name="gastos")
    proveedor = models.ForeignKey(
        Proveedor, null=True, blank=True, on_delete=models.PROTECT, related_name="gastos",
    )

    tipo_documento = models.CharField(max_length=15, choices=TipoDocumento.choices)
    numero_documento = models.CharField(max_length=40, blank=True)

    tasa = models.ForeignKey("cambio.TasaCambio", on_delete=models.PROTECT, related_name="gastos")

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.REGISTRADO)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gastos_registrados",
    )
    fecha_registro = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="gastos_aprobados",
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="gastos_anulados",
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(blank=True)

    # G-3: aprobar un gasto que uno mismo registró exige esta confirmación
    # explícita, salvo que la institución tenga permitir_autoaprobacion=True.
    autoaprobacion_confirmada = models.BooleanField(default=False)
    # Aprobar dejando el saldo del fondo en negativo avisa y pide
    # confirmación (no bloquea), igual que la desviación de montos en Aporte.
    saldo_negativo_confirmado = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "gasto"
        verbose_name_plural = "gastos"
        constraints = [
            models.UniqueConstraint(
                fields=["proveedor", "tipo_documento", "numero_documento"],
                condition=Q(proveedor__isnull=False) & ~Q(numero_documento=""),
                name="gasto_documento_unico_por_proveedor",
            ),
        ]
        indexes = [
            models.Index(fields=["fondo", "fecha"]),
            models.Index(fields=["periodo", "estado"]),
            models.Index(fields=["proveedor", "fecha"]),
            models.Index(fields=["registrado_por", "estado"]),
        ]
        ordering = ["-fecha", "-creado_en"]

    def __str__(self):
        return f"Gasto #{self.pk} — {self.fondo} — {self.monto} {self.moneda}"

    def clean(self):
        errores = {}

        if not self.periodo_id:
            errores["fecha"] = "No hay ningún período escolar activo: actívalo en Configuración."
        elif self.fecha:
            periodo = self.periodo
            if not (periodo.fecha_inicio <= self.fecha <= periodo.fecha_fin):
                errores["fecha"] = "La fecha debe estar dentro del período escolar."
            if periodo.cerrado:
                errores.setdefault("fecha", "No se pueden registrar gastos en un período cerrado.")

        if self.tipo_documento == self.TipoDocumento.SIN_SOPORTE and not self.observacion:
            errores["observacion"] = "Un gasto sin soporte exige una observación que explique por qué."

        if errores:
            raise ValidationError(errores)

    def _autocompletar_periodo(self):
        if not self.periodo_id and self.fecha:
            from core.models import PeriodoEscolar

            self.periodo = (
                PeriodoEscolar.objects.filter(
                    activo=True, fecha_inicio__lte=self.fecha, fecha_fin__gte=self.fecha,
                ).first()
                or PeriodoEscolar.objects.filter(activo=True).first()
            )

    def full_clean(self, *args, **kwargs):
        self._autocompletar_periodo()
        return super().full_clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        self._autocompletar_periodo()
        super().save(*args, **kwargs)

    def recalcular(self):
        """Suma los renglones actuales y guarda la cabecera. Se llama
        explícitamente después de guardar el formset de renglones — no por
        señal, para que sea fácil de probar y de leer."""
        agregados = self.renglones.aggregate(
            monto=Sum("subtotal"), monto_ves=Sum("subtotal_ves"), monto_usd=Sum("subtotal_usd"),
        )
        self.monto = agregados["monto"] or Decimal("0")
        self.monto_ves = agregados["monto_ves"] or Decimal("0")
        self.monto_usd = agregados["monto_usd"] or Decimal("0")
        self.tasa_aplicada = self.tasa.valor
        Gasto.objects.filter(pk=self.pk).update(
            monto=self.monto, monto_ves=self.monto_ves, monto_usd=self.monto_usd, tasa_aplicada=self.tasa_aplicada,
        )

    # --- Máquina de estados --------------------------------------------------

    _TRANSICIONES = {
        Estado.REGISTRADO: {Estado.APROBADO, Estado.ANULADO},
        Estado.APROBADO: {Estado.ANULADO},
    }

    def transicionar(self, nuevo_estado, usuario, motivo=None):
        """Único método que cambia `estado`. Aplica G-3 (segregación de
        funciones) al aprobar y avisa (sin bloquear) si el saldo del fondo
        queda negativo."""
        if nuevo_estado not in self._TRANSICIONES.get(self.estado, set()):
            raise ValidationError(
                f"No se puede pasar de «{self.get_estado_display()}» a «{self.Estado(nuevo_estado).label}»."
            )

        if nuevo_estado == self.Estado.APROBADO:
            if self.renglones.count() == 0 or not self.monto:
                raise ValidationError("El gasto no tiene renglones (o el monto es cero): no se puede aprobar.")

            from core.models import Institucion

            institucion = Institucion.obtener()
            mismo_registrador = self.registrado_por_id == usuario.id
            if mismo_registrador and not institucion.permitir_autoaprobacion and not self.autoaprobacion_confirmada:
                raise ValidationError(
                    "Quien registra un gasto no puede aprobarlo. Confirma explícitamente si de todas formas "
                    "quieres continuar (o pide a otro administrador que lo apruebe)."
                )

            from .services import saldo_fondo

            saldo_ves, saldo_usd = saldo_fondo(self.fondo)
            saldo_ves_proyectado = saldo_ves - self.monto_ves
            saldo_usd_proyectado = saldo_usd - self.monto_usd
            if (saldo_ves_proyectado < 0 or saldo_usd_proyectado < 0) and not self.saldo_negativo_confirmado:
                raise ValidationError(
                    "Aprobar este gasto deja el saldo del fondo en negativo. Confirma explícitamente si de "
                    "todas formas quieres continuar."
                )

            self.aprobado_por = usuario
            self.fecha_aprobacion = timezone.now()
        elif nuevo_estado == self.Estado.ANULADO:
            if not motivo:
                raise ValidationError({"motivo": "Indica el motivo de la anulación."})
            self.motivo_anulacion = motivo
            self.anulado_por = usuario
            self.fecha_anulacion = timezone.now()

        self.estado = nuevo_estado
        self.save()


class DetalleGasto(models.Model):
    """Renglón de un gasto. Mientras el gasto esté «registrado» se puede
    agregar, editar y quitar (G-6); al aprobar quedan congelados."""

    gasto = models.ForeignKey(Gasto, on_delete=models.CASCADE, related_name="renglones")
    producto = models.ForeignKey(
        Producto, null=True, blank=True, on_delete=models.PROTECT, related_name="renglones_gasto",
    )
    descripcion = models.CharField(max_length=200, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    unidad = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name="renglones_gasto")
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=4)
    subtotal = models.DecimalField(max_digits=18, decimal_places=4, editable=False)
    subtotal_ves = models.DecimalField(max_digits=18, decimal_places=4, editable=False)
    subtotal_usd = models.DecimalField(max_digits=18, decimal_places=4, editable=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "renglón de gasto"
        verbose_name_plural = "renglones de gasto"
        constraints = [
            models.CheckConstraint(check=Q(cantidad__gt=0), name="detallegasto_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["producto"]),
            models.Index(fields=["gasto"]),
        ]

    def __str__(self):
        return f"{self.producto or self.descripcion} × {self.cantidad}"

    def clean(self):
        if not self.producto_id and not self.descripcion:
            raise ValidationError({"descripcion": "Indica una descripción si el producto no está en el catálogo."})

    def save(self, *args, **kwargs):
        from cambio.services import convertir

        if self.producto_id and not self.unidad_id:
            self.unidad = self.producto.unidad_default

        self.subtotal = (Decimal(self.cantidad) * Decimal(self.precio_unitario)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP,
        )
        self.subtotal_ves, self.subtotal_usd = convertir(self.subtotal, self.gasto.moneda, self.gasto.tasa.valor)
        super().save(*args, **kwargs)
