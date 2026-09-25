from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Institucion(models.Model):
    """Singleton: una sola fila, usada para el encabezado de recibos y reportes.

    Sin campo de logo (D-05): no se guardan archivos. El logo se sirve
    como estático (static/img/logo.png) en las plantillas.
    """

    nombre = models.CharField(max_length=200)
    rif = models.CharField(max_length=20)
    direccion = models.TextField()
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    permitir_autoaprobacion = models.BooleanField(
        default=False,
        help_text="G-3 (Fase 5): si está apagado (por defecto), quien registra un gasto no puede "
        "aprobarlo — hace falta otro administrador, o confirmar explícitamente la excepción caso "
        "por caso. Actívalo solo si la institución tiene un único administrador.",
    )

    class Meta:
        verbose_name = "institución"
        verbose_name_plural = "institución"

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # No tiene sentido borrar el único registro de la institución.
        pass

    @classmethod
    def obtener(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            "nombre": "",
            "rif": "",
            "direccion": "",
        })
        return obj


class PeriodoEscolar(models.Model):
    nombre = models.CharField(max_length=20, unique=True, help_text="Ej: 2025-2026")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=False)
    cerrado = models.BooleanField(default=False)
    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="periodos_cerrados",
    )
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "período escolar"
        verbose_name_plural = "períodos escolares"
        constraints = [
            models.UniqueConstraint(
                fields=["activo"],
                condition=Q(activo=True),
                name="un_solo_periodo_activo",
            ),
        ]
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio >= self.fecha_fin:
            raise ValidationError("La fecha de inicio debe ser anterior a la fecha de fin.")

        if self.fecha_inicio and self.fecha_fin:
            traslapes = PeriodoEscolar.objects.filter(
                fecha_inicio__lte=self.fecha_fin,
                fecha_fin__gte=self.fecha_inicio,
            ).exclude(pk=self.pk)
            if traslapes.exists():
                raise ValidationError(
                    "Las fechas se traslapan con otro período escolar existente."
                )


class RegistroAuditoria(models.Model):
    """Bitácora de eventos que importan. Solo inserción: nunca se edita ni se borra."""

    class Accion(models.TextChoices):
        LOGIN = "login", "Inicio de sesión"
        LOGIN_FALLIDO = "login_fallido", "Inicio de sesión fallido"
        VERIFICAR = "verificar", "Verificación de aporte"
        OBSERVAR = "observar", "Observación de aporte"
        APROBAR = "aprobar", "Aprobación de gasto"
        ANULAR = "anular", "Anulación"
        EMITIR_RECIBO = "emitir_recibo", "Emisión de recibo"
        CARGAR_TASA = "cargar_tasa", "Carga de tasa de cambio"
        EDITAR_TASA = "editar_tasa", "Corrección de tasa de cambio"
        ACTIVAR_PERIODO = "activar_periodo", "Activación de período"
        CERRAR_PERIODO = "cerrar_periodo", "Cierre de período"
        REABRIR_PERIODO = "reabrir_periodo", "Reapertura de período"
        CREAR_USUARIO = "crear_usuario", "Creación de usuario"
        EDITAR_USUARIO = "editar_usuario", "Edición de usuario"
        RESTABLECER_CLAVE = "restablecer_clave", "Restablecimiento de contraseña"
        ACTIVAR_USUARIO = "activar_usuario", "Activación de usuario"
        DESACTIVAR_USUARIO = "desactivar_usuario", "Desactivación de usuario"
        CREAR_FONDO = "crear_fondo", "Creación de fondo"
        AJUSTAR_SALDO_FONDO = "ajustar_saldo_fondo", "Ajuste de saldo inicial de fondo"
        TRANSFERIR_FONDO = "transferir_fondo", "Transferencia entre fondos"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    accion = models.CharField(max_length=20, choices=Accion.choices)
    modelo = models.CharField(max_length=60, blank=True)
    objeto_id = models.CharField(max_length=64, blank=True)
    descripcion = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "bitácora de auditoría"
        indexes = [
            models.Index(fields=["modelo", "objeto_id"]),
            models.Index(fields=["usuario", "fecha"]),
            models.Index(fields=["accion", "fecha"]),
        ]
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_accion_display()} — {self.fecha:%Y-%m-%d %H:%M}"


class PerfilUsuario(models.Model):
    """Extiende User con el rol (Fase 2). La sección del docente NO vive
    aquí: sale de Seccion.docente_responsable en el período activo, para
    no tener dos lugares que mantener sincronizados al reasignar un
    docente a mitad de año."""

    class Rol(models.TextChoices):
        ADMINISTRADOR = "administrador", "Administrador"
        DOCENTE = "docente", "Docente"
        RESPONSABLE_FONDO = "responsable_fondo", "Responsable de fondo"
        DIRECTOR = "director", "Director"
        AUDITOR = "auditor", "Auditor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rol = models.CharField(max_length=20, choices=Rol.choices)
    fondo = models.ForeignKey(
        "gastos.Fondo", null=True, blank=True, on_delete=models.PROTECT,
        related_name="responsables",
        help_text="Solo para el rol 'Responsable de fondo'.",
    )
    telefono = models.CharField(max_length=20, blank=True)
    debe_cambiar_clave = models.BooleanField(
        default=True, help_text="Se pone en True al crear el usuario; se apaga cuando cambia la clave."
    )

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(rol="responsable_fondo", fondo__isnull=False)
                    | (~Q(rol="responsable_fondo") & Q(fondo__isnull=True))
                ),
                name="fondo_solo_para_responsable_fondo",
            ),
        ]

    def __str__(self):
        return f"{self.user} ({self.get_rol_display()})"

    def clean(self):
        if self.rol == self.Rol.RESPONSABLE_FONDO and not self.fondo_id:
            raise ValidationError("Un responsable de fondo debe tener un fondo asignado.")
        if self.rol != self.Rol.RESPONSABLE_FONDO and self.fondo_id:
            raise ValidationError("Solo el rol 'Responsable de fondo' puede tener un fondo asignado.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._sincronizar_grupo()

    def _sincronizar_grupo(self):
        """El rol es la única fuente de verdad; el Group de Django se
        deriva de él, nunca al revés."""
        grupo, _ = Group.objects.get_or_create(name=self.rol)
        nombres_roles = [valor for valor, _ in self.Rol.choices]
        grupos_de_rol_a_quitar = Group.objects.filter(name__in=nombres_roles).exclude(pk=grupo.pk)
        self.user.groups.remove(*grupos_de_rol_a_quitar)
        self.user.groups.add(grupo)
