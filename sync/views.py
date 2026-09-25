"""Endpoints de sincronización de la cola offline (Fase 7, D-27).

Reciben en JSON lo que `offline-forms.js` guardó en IndexedDB mientras el
dispositivo estaba sin conexión, y lo crean con las mismas reglas que las
pantallas normales (`ingresos:aporte_registrar`, `gastos:gasto_registrar`) —
pero construyendo el modelo directamente en vez de pasar por el
`ModelForm`, porque el payload es JSON, no un POST de formulario.

Idempotentes por `uuid_cliente`: reenviar el mismo payload nunca crea un
segundo registro. Esto es necesario porque Background Sync puede reintentar
un envío cuya respuesta se perdió de vuelta (el servidor sí lo guardó, pero
el navegador no se enteró) — sin esto, ese reintento crearía un duplicado.

Cualquier problema con los datos (inválidos, permiso denegado, referencia
duplicada, lo que sea) se devuelve como 4xx a propósito, nunca como 500: la
cola del cliente (`offline-sync-core.js::enviarUno`) solo reintenta solo
cuando NO hay respuesta del servidor (caída de red). Un 4xx se marca como
«error» y queda esperando que alguien lo revise a mano — si en vez de eso
devolviéramos 500, Background Sync lo reintentaría indefinidamente sin
que nadie se entere de que nunca va a funcionar."""

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from cambio.models import TasaCambio
from gastos.models import DetalleGasto, Gasto
from gastos.views import ROLES_REGISTRO as ROLES_REGISTRO_GASTOS
from ingresos.models import Aporte
from ingresos.views import ROLES_REGISTRO as ROLES_REGISTRO_APORTES


def _rol(usuario):
    return getattr(getattr(usuario, "perfilusuario", None), "rol", None)


def _tiene_rol(usuario, roles):
    return usuario.is_superuser or _rol(usuario) in roles


def _leer_json(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _decimal_o_none(valor):
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def _error_generico(mensaje):
    return JsonResponse({"detalle": mensaje}, status=422)


@login_required
@require_POST
def api_sync_aporte(request):
    if not _tiene_rol(request.user, ROLES_REGISTRO_APORTES):
        raise PermissionDenied("No tienes permiso para registrar aportes.")

    datos = _leer_json(request)
    if datos is None:
        return JsonResponse({"detalle": "JSON inválido."}, status=400)

    uuid_cliente = datos.get("uuid_cliente")
    if not uuid_cliente:
        return JsonResponse({"detalle": "Falta uuid_cliente."}, status=400)

    existente = Aporte.objects.filter(uuid_cliente=uuid_cliente).first()
    if existente:
        return JsonResponse(
            {"resultado": "ya_existia", "id": existente.pk, "estado": existente.estado}, status=200,
        )

    tasa_id = datos.get("tasa") or None
    tasa = TasaCambio.objects.filter(pk=tasa_id).first() if tasa_id else None
    if not tasa:
        return JsonResponse(
            {"detalle": "Datos inválidos.", "errores": {"tasa": ["La tasa usada ya no existe."]}}, status=422,
        )

    aporte = Aporte(
        uuid_cliente=uuid_cliente,
        concepto_id=datos.get("concepto") or None,
        concepto_libre=datos.get("concepto_libre") or "",
        mes_cubierto=datos.get("mes_cubierto") or None,
        monto=_decimal_o_none(datos.get("monto")),
        moneda=datos.get("moneda") or "",
        tasa=tasa,
        forma_pago_id=datos.get("forma_pago") or None,
        fecha_pago=datos.get("fecha_pago") or None,
        banco_destino_id=datos.get("banco_destino") or None,
        banco_origen_id=datos.get("banco_origen") or None,
        referencia=datos.get("referencia") or "",
        telefono_emisor=datos.get("telefono_emisor") or "",
        cedula_titular=datos.get("cedula_titular") or "",
        nombre_titular=datos.get("nombre_titular") or "",
        nota_pago=datos.get("nota_pago") or "",
        entregado_por_id=datos.get("entregado_por") or None,
        entregado_por_nombre=datos.get("entregado_por_nombre") or "",
        inscripcion_id=datos.get("inscripcion") or None,
        desviacion_confirmada=bool(datos.get("desviacion_confirmada")),
        registrado_por=request.user,
        estado=Aporte.Estado.REGISTRADO,
        fecha_registro=timezone.now(),
    )

    try:
        if aporte.monto is not None and aporte.moneda:
            aporte.calcular_montos()
        aporte.full_clean()
        aporte.save()
    except ValidationError as e:
        detalle = e.message_dict if hasattr(e, "message_dict") else {"__all__": e.messages}
        return JsonResponse({"detalle": "Datos inválidos.", "errores": detalle}, status=422)
    except IntegrityError:
        existente = Aporte.objects.filter(uuid_cliente=uuid_cliente).first()
        if existente:
            return JsonResponse(
                {"resultado": "ya_existia", "id": existente.pk, "estado": existente.estado}, status=200,
            )
        return _error_generico("No se pudo guardar (posible referencia duplicada).")
    except ObjectDoesNotExist:
        return _error_generico("Alguno de los datos elegidos ya no existe.")

    return JsonResponse({"resultado": "creado", "id": aporte.pk, "estado": aporte.estado}, status=201)


@login_required
@require_POST
def api_sync_gasto(request):
    if not _tiene_rol(request.user, ROLES_REGISTRO_GASTOS):
        raise PermissionDenied("No tienes permiso para registrar gastos.")

    datos = _leer_json(request)
    if datos is None:
        return JsonResponse({"detalle": "JSON inválido."}, status=400)

    uuid_cliente = datos.get("uuid_cliente")
    if not uuid_cliente:
        return JsonResponse({"detalle": "Falta uuid_cliente."}, status=400)

    existente = Gasto.objects.filter(uuid_cliente=uuid_cliente).first()
    if existente:
        return JsonResponse({"resultado": "ya_existia", "id": existente.pk, "estado": existente.estado}, status=200)

    renglones_datos = datos.get("renglones") or []
    if not renglones_datos:
        return JsonResponse(
            {"detalle": "Datos inválidos.", "errores": {"renglones": ["El gasto no tiene renglones."]}}, status=422,
        )

    fondo_id = datos.get("fondo") or None

    # Mismo criterio que GastoForm (Fase 5, D-14): un responsable de fondo
    # solo puede registrar en su propio fondo, aunque el payload venga
    # manipulado — no basta con que la UI ya lo restrinja.
    if not request.user.is_superuser and _rol(request.user) == "responsable_fondo":
        perfil = getattr(request.user, "perfilusuario", None)
        fondo_permitido = getattr(perfil, "fondo_id", None)
        if not fondo_permitido or str(fondo_permitido) != str(fondo_id):
            raise PermissionDenied("Solo puedes registrar gastos en tu propio fondo.")

    tasa_id = datos.get("tasa") or None
    tasa = TasaCambio.objects.filter(pk=tasa_id).first() if tasa_id else None
    if not tasa:
        return JsonResponse(
            {"detalle": "Datos inválidos.", "errores": {"tasa": ["La tasa usada ya no existe."]}}, status=422,
        )

    gasto = Gasto(
        uuid_cliente=uuid_cliente,
        fecha=datos.get("fecha") or None,
        fondo_id=fondo_id,
        proveedor_id=datos.get("proveedor") or None,
        tipo_documento=datos.get("tipo_documento") or "",
        numero_documento=datos.get("numero_documento") or "",
        moneda=datos.get("moneda") or "",
        tasa=tasa,
        tasa_aplicada=tasa.valor,
        observacion=datos.get("observacion") or "",
        registrado_por=request.user,
        fecha_registro=timezone.now(),
        estado=Gasto.Estado.REGISTRADO,
        monto=Decimal("0"), monto_ves=Decimal("0"), monto_usd=Decimal("0"),
    )

    errores = {}
    try:
        gasto.full_clean()
    except ValidationError as e:
        errores.update(e.message_dict if hasattr(e, "message_dict") else {"__all__": e.messages})
    except ObjectDoesNotExist:
        errores["__all__"] = ["Alguno de los datos elegidos (fondo, proveedor...) ya no existe."]

    detalles = []
    for indice, renglon in enumerate(renglones_datos):
        detalle = DetalleGasto(
            producto_id=renglon.get("producto") or None,
            descripcion=renglon.get("descripcion") or "",
            cantidad=_decimal_o_none(renglon.get("cantidad")),
            unidad_id=renglon.get("unidad") or None,
            precio_unitario=_decimal_o_none(renglon.get("precio_unitario")),
        )
        clave = f"renglon_{indice + 1}"
        if detalle.cantidad is None or detalle.cantidad <= 0:
            errores.setdefault(clave, []).append("Cantidad inválida.")
        if detalle.precio_unitario is None:
            errores.setdefault(clave, []).append("Precio unitario inválido.")
        try:
            detalle.clean()
        except ValidationError as e:
            errores.setdefault(clave, []).extend(e.messages)
        detalles.append(detalle)

    if errores:
        return JsonResponse({"detalle": "Datos inválidos.", "errores": errores}, status=422)

    try:
        with transaction.atomic():
            gasto.save()
            for detalle in detalles:
                detalle.gasto = gasto
                if detalle.producto_id and not detalle.unidad_id:
                    detalle.unidad = detalle.producto.unidad_default
                detalle.save()
            gasto.recalcular()
    except IntegrityError:
        existente = Gasto.objects.filter(uuid_cliente=uuid_cliente).first()
        if existente:
            return JsonResponse(
                {"resultado": "ya_existia", "id": existente.pk, "estado": existente.estado}, status=200,
            )
        return _error_generico("No se pudo guardar (posible documento duplicado para ese proveedor).")
    except ObjectDoesNotExist:
        return _error_generico("Alguno de los datos de un renglón ya no existe.")

    return JsonResponse({"resultado": "creado", "id": gasto.pk, "estado": gasto.estado}, status=201)
