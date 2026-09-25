"""Emisión y anulación de recibos. `Aporte.transicionar()` (en
`ingresos/models.py`) es el único que llama estas funciones — ninguna vista
debe crear o anular un `Recibo` por su cuenta.
"""

from django.db import transaction
from django.utils import timezone

from .models import Recibo, SerieRecibo


def emitir_recibo(aporte, usuario):
    """Asigna el próximo número de la serie del período de `aporte` y crea
    su `Recibo`. Numeración: `select_for_update()` + incremento dentro de
    una transacción — jamás `max()+1` (así 20 verificaciones simultáneas
    salen con 20 números consecutivos, sin huecos ni duplicados)."""
    with transaction.atomic():
        serie, _creada = SerieRecibo.objects.get_or_create(
            periodo=aporte.periodo, defaults={"prefijo": aporte.periodo.nombre},
        )
        serie = SerieRecibo.objects.select_for_update().get(pk=serie.pk)
        serie.ultimo_numero += 1
        serie.save(update_fields=["ultimo_numero"])

        inscripcion = aporte.inscripcion
        docente = None
        if inscripcion and inscripcion.seccion.docente_responsable_id:
            docente = inscripcion.seccion.docente_responsable

        return Recibo.objects.create(
            aporte=aporte,
            serie=serie,
            numero=serie.ultimo_numero,
            numero_texto=f"{serie.prefijo}-{serie.ultimo_numero:06d}",
            fecha_emision=timezone.now(),
            emitido_por=usuario,
            entregado_por_texto=(
                str(aporte.entregado_por) if aporte.entregado_por_id else aporte.entregado_por_nombre
            ),
            estudiante_texto=str(inscripcion.estudiante) if inscripcion else "",
            seccion_texto=str(inscripcion.seccion) if inscripcion else "",
            concepto_texto=str(aporte.concepto) if aporte.concepto_id else aporte.concepto_libre,
            docente_texto=str(docente) if docente else "",
        )


def anular_recibo(aporte, usuario, motivo):
    """Marca el recibo del aporte como anulado, si existe. El número y el
    recibo mismo se conservan (no se borran ni se reutiliza el número)."""
    recibo = getattr(aporte, "recibo", None)
    if recibo is not None and not recibo.anulado:
        recibo.anulado = True
        recibo.motivo_anulacion = motivo
        recibo.anulado_por = usuario
        recibo.fecha_anulacion = timezone.now()
        recibo.save(update_fields=["anulado", "motivo_anulacion", "anulado_por", "fecha_anulacion"])
