from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Grado
from core.models import Institucion, PeriodoEscolar
from gastos.models import Fondo

# Listado estándar del sistema educativo venezolano.
# nombre, nivel, orden (orden define la secuencia de promoción, Fase 6)
GRADOS = [
    ("1er Nivel", Grado.Nivel.INICIAL, 1),
    ("2do Nivel", Grado.Nivel.INICIAL, 2),
    ("3er Nivel", Grado.Nivel.INICIAL, 3),
    ("1er Grado", Grado.Nivel.PRIMARIA, 4),
    ("2do Grado", Grado.Nivel.PRIMARIA, 5),
    ("3er Grado", Grado.Nivel.PRIMARIA, 6),
    ("4to Grado", Grado.Nivel.PRIMARIA, 7),
    ("5to Grado", Grado.Nivel.PRIMARIA, 8),
    ("6to Grado", Grado.Nivel.PRIMARIA, 9),
    ("1er Año", Grado.Nivel.MEDIA, 10),
    ("2do Año", Grado.Nivel.MEDIA, 11),
    ("3er Año", Grado.Nivel.MEDIA, 12),
    ("4to Año", Grado.Nivel.MEDIA, 13),
    ("5to Año", Grado.Nivel.MEDIA, 14),
]


class Command(BaseCommand):
    help = (
        "Carga los datos iniciales de Edumia: Institución (valores de ejemplo, "
        "editables luego en el admin), Período escolar activo, el listado "
        "estándar de Grados (Inicial, Primaria, Media) y el Fondo General. "
        "Es idempotente: se puede volver a ejecutar sin duplicar datos."
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            self._crear_institucion()
            self._crear_periodo()
            self._crear_grados()
            self._crear_fondo_general()

    def _crear_institucion(self):
        inst = Institucion.obtener()
        if not inst.nombre:
            inst.nombre = "Institución Educativa (pendiente de nombre real)"
            inst.rif = "J-00000000-0"
            inst.direccion = "Dirección pendiente de completar"
            inst.save()
            self.stdout.write(self.style.WARNING(
                "Institución creada con datos de ejemplo. Edítala en /admin/ "
                "con el nombre, RIF y dirección reales antes de emitir el "
                "primer recibo (Fase 4)."
            ))
        else:
            self.stdout.write("Institución ya existía (tiene nombre), no se modificó.")

    def _crear_periodo(self):
        if PeriodoEscolar.objects.filter(activo=True).exists():
            self.stdout.write("Ya existe un período escolar activo, no se creó otro.")
            return
        PeriodoEscolar.objects.get_or_create(
            nombre="2026-2027",
            defaults={
                "fecha_inicio": date(2026, 9, 1),
                "fecha_fin": date(2027, 7, 31),
                "activo": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            "Período escolar '2026-2027' creado y marcado activo. Ajusta las "
            "fechas en /admin/ si no coinciden con el calendario real."
        ))

    def _crear_grados(self):
        creados = 0
        for nombre, nivel, orden in GRADOS:
            _, created = Grado.objects.get_or_create(
                nombre=nombre, nivel=nivel, defaults={"orden": orden},
            )
            if created:
                creados += 1
        existentes = len(GRADOS) - creados
        self.stdout.write(self.style.SUCCESS(
            f"Grados: {creados} creados, {existentes} ya existían."
        ))

    def _crear_fondo_general(self):
        _, created = Fondo.objects.get_or_create(
            es_general=True, defaults={"nombre": "General", "descripcion": "Fondo general de la institución"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Fondo General creado."))
        else:
            self.stdout.write("El Fondo General ya existía, no se modificó.")
