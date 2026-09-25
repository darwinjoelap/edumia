"""Bitácora de auditoría (Fase 8): un solo punto de entrada para registrar
un evento en `RegistroAuditoria`. El modelo existía desde la Fase 1 pero
nada lo llamaba todavía — nunca quedó conectado a ningún login, verificación
ni anulación real. Este módulo es lo que faltaba conectar, junto con las
llamadas agregadas en las vistas correspondientes (ingresos, gastos, cambio,
core) y las señales de login/login fallido (`core/signals.py`).

Se llama siempre con el `request` a mano (nunca desde los modelos): así se
puede sacar el usuario y la IP sin que `Aporte`/`Gasto`/`TasaCambio` tengan
que saber nada de HTTP."""


def obtener_ip(request):
    """IP real del cliente. Render (como casi cualquier hosting gratuito)
    hace de proxy: `REMOTE_ADDR` ahí sería la IP interna de Render, no la
    del usuario, así que se prefiere `X-Forwarded-For` cuando existe."""
    if request is None:
        return None
    adelante = request.META.get("HTTP_X_FORWARDED_FOR")
    if adelante:
        return adelante.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def registrar(request, accion, *, modelo="", objeto_id="", descripcion=""):
    """Crea una fila en la bitácora. No lanza si algo falla (una auditoría
    que rompe el flujo normal sería peor que no tenerla): cualquier error
    queda silenciado a propósito, ya que esto nunca debe impedir que un
    aporte se verifique o un gasto se apruebe."""
    from .models import RegistroAuditoria

    usuario = getattr(request, "user", None)
    if usuario is not None and not usuario.is_authenticated:
        usuario = None

    try:
        RegistroAuditoria.objects.create(
            usuario=usuario,
            accion=accion,
            modelo=modelo,
            objeto_id=str(objeto_id) if objeto_id else "",
            descripcion=descripcion,
            ip=obtener_ip(request),
        )
    except Exception:
        pass
