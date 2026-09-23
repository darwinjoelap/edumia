"""Promoción masiva de estudiantes al siguiente período.

D-21 (revisión pedida explícitamente): en la práctica el personal arma las
secciones a mano cada año — un curso no necesariamente se mueve completo a
la sección del mismo nombre en el grado siguiente. Por eso esto ya NO
empareja automáticamente por nombre: junta a los estudiantes por sección de
origen y deja que el usuario elija, estudiante por estudiante (con un
"aplicar a todos" para el caso común), a qué sección destino va cada uno.
El grado de mayor `orden` (sin grado siguiente) no tiene nada que elegir:
sus estudiantes se marcan "egresado" directo.

Flujo de dos pasos, igual que antes: calcular_plan_manual() solo lee la
base de datos (para armar el formulario de asignación) y
ejecutar_promocion_manual() es lo único que escribe, y solo se llama tras
la confirmación del usuario con las asignaciones ya elegidas.
"""
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction

from .models import Grado, Inscripcion, Seccion


@dataclass
class FilaEstudiante:
    inscripcion: Inscripcion
    estudiante: object
    sugerencia_id: int | None = None


@dataclass
class GrupoSeccion:
    seccion_origen: Seccion
    grado_siguiente: Grado | None
    secciones_destino: list = field(default_factory=list)
    filas: list = field(default_factory=list)

    @property
    def cantidad(self):
        return len(self.filas)

    @property
    def sin_secciones_destino(self):
        return self.grado_siguiente is not None and not self.secciones_destino


def _secciones_destino_por_grado(periodo_destino):
    """grado_id -> lista de secciones activas de ese grado en periodo_destino."""
    secciones = (
        Seccion.objects.filter(periodo=periodo_destino, activa=True)
        .select_related("grado")
        .order_by("nombre")
    )
    mapa = {}
    for seccion in secciones:
        mapa.setdefault(seccion.grado_id, []).append(seccion)
    return mapa


def calcular_plan_manual(periodo_origen, periodo_destino):
    """Solo lectura: un grupo por cada sección del período de origen que
    tenga al menos un estudiante con inscripción activa, con la lista de
    esos estudiantes y las secciones destino disponibles para elegir."""
    grupos = []
    secciones_origen = (
        Seccion.objects.filter(periodo=periodo_origen)
        .select_related("grado")
        .order_by("grado__orden", "nombre")
    )
    destino_por_grado = _secciones_destino_por_grado(periodo_destino)

    for seccion in secciones_origen:
        inscripciones = list(
            Inscripcion.objects.filter(
                seccion=seccion, periodo=periodo_origen, estado=Inscripcion.Estado.ACTIVO
            )
            .select_related("estudiante")
            .order_by("estudiante__apellidos", "estudiante__nombres")
        )
        if not inscripciones:
            continue

        grado_siguiente = Grado.objects.filter(orden=seccion.grado.orden + 1).first()
        secciones_destino = destino_por_grado.get(grado_siguiente.id, []) if grado_siguiente else []

        sugerida_id = None
        if grado_siguiente:
            sugerida = next((s for s in secciones_destino if s.nombre == seccion.nombre), None)
            sugerida_id = sugerida.id if sugerida else None

        filas = [
            FilaEstudiante(insc, insc.estudiante, sugerida_id)
            for insc in inscripciones
        ]
        grupos.append(GrupoSeccion(seccion, grado_siguiente, secciones_destino, filas))

    return grupos


def ejecutar_promocion_manual(periodo_origen, periodo_destino, fecha, asignaciones):
    """Aplica las asignaciones elegidas por el usuario.

    `asignaciones`: {estudiante_id: seccion_destino_id (o None si no se
    eligió)}. Es seguro volver a correrla: a un estudiante ya promovido o
    egresado no se le vuelve a tocar, y los que quedaron sin sección elegida
    se pueden completar en una corrida posterior.
    """
    resultado = {"promovidos": 0, "egresados": 0, "ya_existian": 0, "sin_destino": 0}

    for grupo in calcular_plan_manual(periodo_origen, periodo_destino):
        for fila in grupo.filas:
            estudiante = fila.estudiante

            if grupo.grado_siguiente is None:
                if fila.inscripcion.estado != Inscripcion.Estado.EGRESADO:
                    fila.inscripcion.estado = Inscripcion.Estado.EGRESADO
                    fila.inscripcion.save(update_fields=["estado"])
                    resultado["egresados"] += 1
                continue

            ya_tiene = Inscripcion.objects.filter(
                estudiante=estudiante, periodo=periodo_destino
            ).exists()
            if ya_tiene:
                resultado["ya_existian"] += 1
                continue

            seccion_destino_id = asignaciones.get(estudiante.id)
            if not seccion_destino_id:
                resultado["sin_destino"] += 1
                continue
            try:
                with transaction.atomic():
                    Inscripcion.objects.create(
                        estudiante=estudiante,
                        seccion_id=seccion_destino_id,
                        periodo=periodo_destino,
                        fecha=fecha,
                    )
                resultado["promovidos"] += 1
            except IntegrityError:
                # Carrera con otra confirmación simultánea, o el estudiante
                # ya tenía inscripción en el destino (caso raro).
                resultado["ya_existian"] += 1

    return resultado
