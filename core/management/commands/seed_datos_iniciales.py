from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Grado
from core.models import Institucion, PeriodoEscolar
from gastos.models import Fondo, UnidadMedida
from ingresos.models import Banco, FormaPago

# Bancos venezolanos más comunes (código SUDEBAN). Lista de arranque: si algún
# código está desactualizado, se corrige desde /admin/ sin tocar código.
BANCOS = [
    ("0102", "Banco de Venezuela"),
    ("0104", "Banco Venezolano de Crédito"),
    ("0105", "Banco Mercantil"),
    ("0108", "Banco Provincial"),
    ("0114", "Bancaribe"),
    ("0115", "Banco Exterior"),
    ("0116", "Banco Occidental de Descuento"),
    ("0128", "Banco Caroní"),
    ("0134", "Banesco"),
    ("0137", "Banco Sofitasa"),
    ("0138", "Banco Plaza"),
    ("0151", "Banco Fondo Común"),
    ("0156", "100% Banco"),
    ("0157", "DelSur"),
    ("0163", "Banco del Tesoro"),
    ("0166", "Banco Agrícola de Venezuela"),
    ("0168", "Bancrecer"),
    ("0169", "Mi Banco"),
    ("0171", "Banco Activo"),
    ("0172", "Bancamiga"),
    ("0174", "Banplus"),
    ("0175", "Banco Bicentenario"),
    ("0177", "Banco de la Fuerza Armada Nacional Bolivariana"),
    ("0191", "Banco Nacional de Crédito"),
]

# Formas de pago sugeridas (docs/MODELOS_cambio_ingresos.md). Cada tupla:
# nombre, moneda_fija, requiere_banco_destino, requiere_banco_origen,
# requiere_referencia, requiere_telefono, requiere_cedula
FORMAS_PAGO = [
    ("Efectivo (Bs.)", "VES", False, False, False, False, False),
    ("Divisa efectivo", "USD", False, False, False, False, False),
    ("Pago móvil", "VES", True, True, True, True, True),
    ("Transferencia", "VES", True, False, True, False, True),
    ("Zelle", "USD", False, False, True, False, False),
]

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

# Unidades de medida (docs/MODELOS_gastos.md, Fase 5). nombre, abreviatura.
# Ampliado en la Fase 8 (D-31) para cubrir los tipos de gasto típicos de una
# institución: alimentos, limpieza, papelería/oficina, mantenimiento y
# servicios (mano de obra, montos globales sin cantidad real).
UNIDADES_MEDIDA = [
    ("Kilogramo", "Kg"),
    ("Gramo", "g"),
    ("Litro", "Litro"),
    ("Mililitro", "ml"),
    ("Unidad", "Unidad"),
    ("Par", "Par"),
    ("Docena", "Docena"),
    ("Bulto", "Bulto"),
    ("Saco", "Saco"),
    ("Paquete", "Paquete"),
    ("Caja", "Caja"),
    ("Resma", "Resma"),
    ("Rollo", "Rollo"),
    ("Galón", "Galón"),
    ("Metro", "m"),
    ("Metro cuadrado", "m2"),
    ("Frasco", "Frasco"),
    ("Tubo", "Tubo"),
    ("Bolsa", "Bolsa"),
    ("Kit", "Kit"),
    ("Hora", "Hora"),
    ("Servicio", "Servicio"),
    ("Global", "Global"),
]


class Command(BaseCommand):
    help = (
        "Carga los datos iniciales de Edumia: Institución (valores de ejemplo, "
        "editables luego en el admin), Período escolar activo, el listado "
        "estándar de Grados (Inicial, Primaria, Media), el Fondo General, el "
        "catálogo de Bancos y Formas de pago (Fase 3) y, desde la Fase 5, las "
        "Unidades de medida de gastos. "
        "Es idempotente: se puede volver a ejecutar sin duplicar datos."
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            self._crear_institucion()
            self._crear_periodo()
            self._crear_grados()
            self._crear_fondo_general()
            self._crear_bancos()
            self._crear_formas_pago()
            self._crear_unidades_medida()

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

    def _crear_bancos(self):
        creados = 0
        for codigo, nombre in BANCOS:
            _, created = Banco.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
            if created:
                creados += 1
        existentes = len(BANCOS) - creados
        self.stdout.write(self.style.SUCCESS(
            f"Bancos: {creados} creados, {existentes} ya existían."
        ))

    def _crear_formas_pago(self):
        creadas = 0
        for nombre, moneda_fija, req_destino, req_origen, req_ref, req_tel, req_ced in FORMAS_PAGO:
            _, created = FormaPago.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "moneda_fija": moneda_fija,
                    "requiere_banco_destino": req_destino,
                    "requiere_banco_origen": req_origen,
                    "requiere_referencia": req_ref,
                    "requiere_telefono": req_tel,
                    "requiere_cedula": req_ced,
                },
            )
            if created:
                creadas += 1
        existentes = len(FORMAS_PAGO) - creadas
        self.stdout.write(self.style.SUCCESS(
            f"Formas de pago: {creadas} creadas, {existentes} ya existían."
        ))

    def _crear_unidades_medida(self):
        creadas = 0
        for nombre, abreviatura in UNIDADES_MEDIDA:
            _, created = UnidadMedida.objects.get_or_create(
                nombre=nombre, defaults={"abreviatura": abreviatura},
            )
            if created:
                creadas += 1
        existentes = len(UNIDADES_MEDIDA) - creadas
        self.stdout.write(self.style.SUCCESS(
            f"Unidades de medida: {creadas} creadas, {existentes} ya existían."
        ))
