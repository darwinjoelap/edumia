"""Promoción masiva de estudiantes al siguiente período (cierre de la Fase 1).

Regla: el "siguiente grado" es el de `orden` inmediato superior en Grado.
Como el fixture de seed_datos_iniciales numera el orden de forma continua
(Inicial -> Primaria -> Media), esto encadena los niveles automáticamente
sin tener que tratarlos como casos especiales. El grado de mayor orden
(5to Año) no tiene siguiente: sus estudiantes quedan "egresados" en vez de
promovidos a una sección nueva.

Flujo de dos pasos, igual que la importación de estudiantes: calcular_plan()
solo lee la base de datos (para la vista previa) y ejecutar_promocion() es
lo único que escribe, y solo se llama tras la confirmación del usuario.
"""
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from .models import Grado, Inscripcion, Seccion


@dataclass
class FilaPromocion:
    seccion_origen: Seccion
    cantidad_activos: int
    accion: str  # "promueve" | "egresa" | "sin_destino"
    seccion_destino: Seccion | None = None


def calcular_plan(periodo_origen, periodo_destino):
    """Solo lectura: una fila por cada sección del período de origen que
    tenga al menos un estudiante con inscripción activa."""
    filas = []
    secciones_origen = (
        Seccion.objects.filter(periodo=periodo_origen)
        .select_related("grado")
        .order_by("grado__orden", "nombre")
    )
    for seccion in secciones_origen:
        cantidad = Inscripcion.objects.filter(
            seccion=seccion, periodo=periodo_origen, estado=Inscripcion.Estado.ACTIVO
        ).count()
        if cantidad == 0:
            continue

        grado_siguiente = Grado.objects.filter(orden=seccion.grado.orden + 1).first()
        if grado_siguiente is None:
            filas.append(FilaPromocion(seccion, cantidad, "egresa"))
            continue

        seccion_destino = Seccion.objects.filter(
            periodo=periodo_destino, grado=grado_siguiente, nombre=seccion.nombre
        ).first()
        if seccion_destino:
            filas.append(FilaPromocion(seccion, cantidad, "promueve", seccion_destino))
        else:
            filas.append(FilaPromocion(seccion, cantidad, "sin_destino"))
    return filas


def ejecutar_promocion(periodo_origen, periodo_destino, fecha):
    """Aplica el plan calculado por calcular_plan(). Es seguro volver a
    correrla dos veces: a un estudiante ya promovido/egresado no se le
    vuelve a tocar."""
    resultado = {"promovidos": 0, "egresados": 0, "ya_existian": 0, "sin_destino": 0}

    for fila in calcular_plan(periodo_origen, periodo_destino):
        if fila.accion == "sin_destino":
            resultado["sin_destino"] += fila.cantidad_activos
            continue

        inscripciones = Inscripcion.objects.filter(
            seccion=fila.seccion_origen, periodo=periodo_origen, estado=Inscripcion.Estado.ACTIVO
        ).select_related("estudiante")

        for inscripcion in inscripciones:
            if fila.accion == "egresa":
                if inscripcion.estado != Inscripcion.Estado.EGRESADO:
                    inscripcion.estado = Inscripcion.Estado.EGRESADO
                    inscripcion.save(update_fields=["estado"])
                    resultado["egresados"] += 1
                continue

            # accion == "promueve"
            ya_tiene = Inscripcion.objects.filter(
                estudiante=inscripcion.estudiante, periodo=periodo_destino
            ).exists()
            if ya_tiene:
                resultado["ya_existian"] += 1
                continue
            try:
                with transaction.atomic():
                    Inscripcion.objects.create(
                        estudiante=inscripcion.estudiante,
                        seccion=fila.seccion_destino,
                        periodo=periodo_destino,
                        fecha=fecha,
                    )
                resultado["promovidos"] += 1
            except IntegrityError:
                resultado["ya_existian"] += 1

    return resultado
