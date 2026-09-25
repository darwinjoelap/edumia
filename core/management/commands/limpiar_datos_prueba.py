"""Fase 8 (D-31): borra los datos de prueba antes de pasarle el sistema al
instituto, dejando solo lo necesario para que empiecen a usarlo de cero.

Se borra: estudiantes, representantes, inscripciones, aportes, gastos,
recibos, series de recibo, tasas de cambio, la bitácora de auditoría, y los
usuarios de prueba (cualquiera con PerfilUsuario que no sea superusuario ni
esté en --mantener-usuario).

Se conserva: la Institución, los períodos escolares, los grados y secciones
(quedan vacíos de estudiantes, pero no se borran), y todos los catálogos
(bancos, formas de pago, conceptos de ingreso, montos por concepto,
categorías de gasto, productos, proveedores, unidades de medida, fondos).

Por defecto NO borra nada: solo muestra cuántas filas de cada tipo hay y
cuántas se borrarían. Hace falta pasar --confirmar para que borre de verdad.
Uso típico (igual que las otras tareas de base de datos, con la variable
DATABASE_URL apuntando a Neon `production`):

    python manage.py limpiar_datos_prueba                       # solo cuenta, no borra nada
    python manage.py limpiar_datos_prueba --confirmar            # borra, conserva solo superusuarios
    python manage.py limpiar_datos_prueba --confirmar --mantener-usuario admin,rectora
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import Estudiante, EstudianteRepresentante, Inscripcion, Representante
from cambio.models import TasaCambio
from core.models import RegistroAuditoria
from gastos.models import Gasto
from ingresos.models import Aporte
from recibos.models import Recibo, SerieRecibo


class Command(BaseCommand):
    help = "Borra los datos de prueba (Fase 8, D-31) antes de pasarle el sistema al instituto. Sin --confirmar solo cuenta."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar", action="store_true",
            help="Borra de verdad. Sin esto, el comando solo muestra los conteos.",
        )
        parser.add_argument(
            "--mantener-usuario", default="",
            help="Nombres de usuario (además de los superusuarios) que NO se deben borrar, separados por comas.",
        )

    def handle(self, *args, **options):
        confirmar = options["confirmar"]
        mantener = {u.strip() for u in options["mantener_usuario"].split(",") if u.strip()}

        User = get_user_model()
        usuarios_a_borrar = User.objects.filter(
            perfilusuario__isnull=False, is_superuser=False,
        ).exclude(username__in=mantener)

        conteos = {
            "Bitácora de auditoría": RegistroAuditoria.objects.count(),
            "Recibos": Recibo.objects.count(),
            "Series de recibo": SerieRecibo.objects.count(),
            "Aportes": Aporte.objects.count(),
            "Gastos (y sus renglones)": Gasto.objects.count(),
            "Tasas de cambio": TasaCambio.objects.count(),
            "Inscripciones": Inscripcion.objects.count(),
            "Estudiantes": Estudiante.objects.count(),
            "Representantes": Representante.objects.count(),
            "Usuarios de prueba": usuarios_a_borrar.count(),
        }

        self.stdout.write("Esto es lo que hay actualmente:")
        for etiqueta, cantidad in conteos.items():
            self.stdout.write(f"  {etiqueta}: {cantidad}")

        superusuarios = list(User.objects.filter(is_superuser=True).values_list("username", flat=True))
        self.stdout.write(self.style.WARNING(
            f"\nSe van a CONSERVAR siempre los superusuarios: {', '.join(superusuarios) or '(ninguno)'}"
            + (f" y además: {', '.join(sorted(mantener))}" if mantener else "")
        ))
        self.stdout.write(
            "Se conservan sin tocar: Institución, períodos escolares, grados, secciones "
            "(quedan vacías de estudiantes) y todos los catálogos (bancos, formas de pago, "
            "conceptos, montos por concepto, categorías de gasto, productos, proveedores, "
            "unidades de medida, fondos)."
        )

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                "\nNo se borró nada (falta --confirmar). Vuelve a correr el comando con "
                "--confirmar cuando quieras aplicar el borrado de verdad."
            ))
            return

        with transaction.atomic():
            RegistroAuditoria.objects.all().delete()
            Recibo.objects.all().delete()
            SerieRecibo.objects.all().delete()
            Aporte.objects.all().delete()
            Gasto.objects.all().delete()  # DetalleGasto se borra en cascada
            TasaCambio.objects.all().delete()
            Inscripcion.objects.all().delete()
            Estudiante.objects.all().delete()  # EstudianteRepresentante se borra en cascada
            Representante.objects.all().delete()
            cantidad_usuarios, _ = usuarios_a_borrar.delete()  # PerfilUsuario se borra en cascada

        self.stdout.write(self.style.SUCCESS(
            f"\nListo. Se borraron los datos de prueba ({cantidad_usuarios} usuarios incluidos). "
            "El sistema queda con la Institución, los catálogos y los períodos/grados/secciones "
            "tal como estaban, listo para que el instituto empiece a cargar datos reales."
        ))
