from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.utils import normalizar_cedula, normalizar_telefono


class Grado(models.Model):
    class Nivel(models.TextChoices):
        INICIAL = "inicial", "Inicial"
        PRIMARIA = "primaria", "Primaria"
        MEDIA = "media", "Media"

    nombre = models.CharField(max_length=50, help_text="Ej: 5to grado")
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    orden = models.PositiveSmallIntegerField(
        help_text="Define el orden de promoción: el siguiente grado es el de orden inmediato superior."
    )

    class Meta:
        verbose_name = "grado"
        verbose_name_plural = "grados"
        constraints = [
            models.UniqueConstraint(fields=["nombre", "nivel"], name="grado_unico_por_nivel"),
        ]
        ordering = ["orden"]

    def __str__(self):
        return self.nombre


class Seccion(models.Model):
    grado = models.ForeignKey(Grado, on_delete=models.PROTECT, related_name="secciones")
    periodo = models.ForeignKey(
        "core.PeriodoEscolar", on_delete=models.PROTECT, related_name="secciones",
    )
    nombre = models.CharField(max_length=10, help_text="Ej: A, B, U")
    docente_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="secciones_a_cargo",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "sección"
        verbose_name_plural = "secciones"
        constraints = [
            models.UniqueConstraint(
                fields=["grado", "nombre", "periodo"], name="seccion_unica_por_periodo",
            ),
        ]
        indexes = [
            models.Index(fields=["periodo", "docente_responsable"]),
        ]
        ordering = ["periodo", "grado__orden", "nombre"]

    def __str__(self):
        return f"{self.grado} \"{self.nombre}\" ({self.periodo})"

    def clean(self):
        # PerfilUsuario todavía no existe en esta fase (llega en la Fase 2).
        # Cuando exista, se valida que el usuario tenga rol "docente"; hasta
        # entonces, no hay nada que verificar y no debe romper el formulario.
        if self.docente_responsable_id and hasattr(self.docente_responsable, "perfilusuario"):
            perfil = self.docente_responsable.perfilusuario
            if perfil.rol != "docente":
                raise ValidationError(
                    "El docente responsable debe tener rol 'docente'."
                )


class Estudiante(models.Model):
    class Sexo(models.TextChoices):
        M = "M", "Masculino"
        F = "F", "Femenino"

    cedula_escolar = models.CharField(max_length=20, null=True, blank=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    sexo = models.CharField(max_length=1, choices=Sexo.choices)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "estudiante"
        verbose_name_plural = "estudiantes"
        constraints = [
            models.UniqueConstraint(
                fields=["cedula_escolar"],
                condition=Q(cedula_escolar__isnull=False),
                name="cedula_escolar_unica_si_existe",
            ),
        ]
        indexes = [
            models.Index(fields=["apellidos", "nombres"]),
        ]
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres}"

    def save(self, *args, **kwargs):
        self.cedula_escolar = normalizar_cedula(self.cedula_escolar)
        self.nombres = self.nombres.strip().title()
        self.apellidos = self.apellidos.strip().title()
        super().save(*args, **kwargs)


class Representante(models.Model):
    cedula = models.CharField(max_length=20, null=True, blank=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=11, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "representante"
        verbose_name_plural = "representantes"
        constraints = [
            models.UniqueConstraint(
                fields=["cedula"],
                condition=Q(cedula__isnull=False),
                name="cedula_representante_unica_si_existe",
            ),
        ]
        indexes = [
            models.Index(fields=["apellidos", "nombres"]),
        ]
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres}"

    def save(self, *args, **kwargs):
        self.cedula = normalizar_cedula(self.cedula)
        self.telefono = normalizar_telefono(self.telefono)
        self.nombres = self.nombres.strip().title()
        self.apellidos = self.apellidos.strip().title()
        super().save(*args, **kwargs)


class EstudianteRepresentante(models.Model):
    class Parentesco(models.TextChoices):
        MADRE = "madre", "Madre"
        PADRE = "padre", "Padre"
        ABUELO_A = "abuelo_a", "Abuelo/a"
        TIO_A = "tio_a", "Tío/a"
        HERMANO_A = "hermano_a", "Hermano/a"
        OTRO = "otro", "Otro"

    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.CASCADE, related_name="representantes",
    )
    representante = models.ForeignKey(
        Representante, on_delete=models.PROTECT, related_name="estudiantes",
    )
    parentesco = models.CharField(max_length=10, choices=Parentesco.choices)
    es_principal = models.BooleanField(default=False)

    class Meta:
        verbose_name = "vínculo estudiante-representante"
        verbose_name_plural = "vínculos estudiante-representante"
        constraints = [
            models.UniqueConstraint(
                fields=["estudiante", "representante"], name="vinculo_unico",
            ),
            models.UniqueConstraint(
                fields=["estudiante"],
                condition=Q(es_principal=True),
                name="un_solo_principal_por_estudiante",
            ),
        ]

    def __str__(self):
        return f"{self.representante} — {self.get_parentesco_display()} de {self.estudiante}"

    def save(self, *args, **kwargs):
        # El primer vínculo de un estudiante queda como principal automáticamente.
        if not self.pk and not EstudianteRepresentante.objects.filter(
            estudiante=self.estudiante
        ).exists():
            self.es_principal = True
        super().save(*args, **kwargs)


class Inscripcion(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        RETIRADO = "retirado", "Retirado"
        EGRESADO = "egresado", "Egresado"

    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.PROTECT, related_name="inscripciones",
    )
    seccion = models.ForeignKey(
        Seccion, on_delete=models.PROTECT, related_name="inscripciones",
    )
    periodo = models.ForeignKey(
        "core.PeriodoEscolar", on_delete=models.PROTECT, related_name="inscripciones",
        help_text="Denormalizado desde seccion.periodo, para filtrar sin JOIN.",
    )
    fecha = models.DateField()
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.ACTIVO,
    )
    fecha_retiro = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "inscripción"
        verbose_name_plural = "inscripciones"
        constraints = [
            models.UniqueConstraint(
                fields=["estudiante", "periodo"], name="una_inscripcion_por_periodo",
            ),
        ]
        indexes = [
            models.Index(fields=["periodo", "estado"]),
            models.Index(fields=["seccion", "estado"]),
        ]
        ordering = ["-periodo__fecha_inicio", "seccion", "estudiante"]

    def __str__(self):
        return f"{self.estudiante} — {self.seccion}"

    def clean(self):
        if self.seccion_id and self.periodo_id and self.seccion.periodo_id != self.periodo_id:
            raise ValidationError("El período debe coincidir con el período de la sección.")
        if self.estado == self.Estado.RETIRADO and not self.fecha_retiro:
            raise ValidationError("Un estudiante retirado debe tener fecha de retiro.")
