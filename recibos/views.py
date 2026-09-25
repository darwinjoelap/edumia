import base64
import io

import qrcode
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from cambio.services import formatear
from core.mixins import requiere_rol
from core.models import Institucion
from ingresos.views import ROLES_HISTORIAL

from .models import Recibo

# Quién puede ver/reimprimir un recibo desde el sistema: los mismos roles
# que pueden ver el historial completo de aportes (además del superusuario).
ROLES_VER_RECIBO = ROLES_HISTORIAL


def _qr_base64(url: str) -> str:
    """PNG del QR codificado en base64, para incrustarlo como <img> sin
    depender de un archivo aparte (así también sale intacto al descargar
    el recibo como imagen)."""
    imagen = qrcode.make(url, box_size=8, border=1)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _montos_formateados(aporte):
    """(monto principal con su moneda, monto equivalente en la otra moneda)
    ya formateados en es-VE, para no ensuciar la plantilla con aritmética."""
    principal = f"{formatear(aporte.monto)} {'Bs.' if aporte.moneda == 'VES' else '$'}"
    if aporte.moneda == "VES":
        equivalente = f"≈ $ {formatear(aporte.monto_usd)}"
    else:
        equivalente = f"≈ Bs. {formatear(aporte.monto_ves)}"
    return principal, equivalente


@requiere_rol(*ROLES_VER_RECIBO)
def recibo_detalle(request, pk):
    """Vista del recibo para el personal de la institución: se puede
    imprimir (media carta) o descargar como imagen para compartir — mismo
    diseño en los dos casos. También sirve para reimprimir en cualquier
    momento, tantas veces como haga falta."""
    recibo = get_object_or_404(
        Recibo.objects.select_related(
            "aporte", "aporte__concepto", "aporte__forma_pago", "serie",
        ),
        pk=pk,
    )
    url_publica = request.build_absolute_uri(
        reverse("recibos:recibo_publico", args=[recibo.uuid]),
    )
    monto_principal, monto_equivalente = _montos_formateados(recibo.aporte)
    return render(request, "recibos/recibo_detalle.html", {
        "recibo": recibo,
        "aporte": recibo.aporte,
        "institucion": Institucion.obtener(),
        "qr_base64": _qr_base64(url_publica),
        "url_publica": url_publica,
        "monto_principal": monto_principal,
        "monto_equivalente": monto_equivalente,
    })


def recibo_publico(request, uuid):
    """Verificación pública por UUID (sin login): lo que se ve al escanear
    el QR del recibo. Muestra el mínimo — número, fecha, monto, concepto,
    estudiante (si aplica) y estado — nunca cédulas ni teléfonos, que ni
    siquiera se copian a `Recibo`."""
    recibo = get_object_or_404(
        Recibo.objects.select_related("aporte", "aporte__concepto", "serie"),
        uuid=uuid,
    )
    monto_principal, monto_equivalente = _montos_formateados(recibo.aporte)
    return render(request, "recibos/recibo_publico.html", {
        "recibo": recibo,
        "aporte": recibo.aporte,
        "institucion": Institucion.obtener(),
        "monto_principal": monto_principal,
        "monto_equivalente": monto_equivalente,
    })
