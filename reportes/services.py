"""Motor de filtros compartido y cálculos de la Fase 6 (Reportes y balance).

No hay modelos propios en esta app: todo se calcula al vuelo sobre `Aporte`
(ingresos) y `Gasto`/`DetalleGasto` (gastos), reutilizando `gastos.services`
para el saldo por fondo (misma fuente de verdad que ya usa el dashboard).
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth

from gastos.models import DetalleGasto, Fondo, Gasto
from gastos.services import saldo_fondo
from ingresos.models import Aporte

CERO = Decimal("0")


def rango_por_defecto():
    """(fecha_inicio, fecha_fin) por defecto cuando el usuario no elige
    ninguno: los últimos 30 días hasta hoy. Simple y predecible; no depende
    de si hay un período activo (un reporte puede pedirse fuera de época)."""
    hoy = date.today()
    return hoy - timedelta(days=30), hoy


def parsear_rango(request):
    """Lee `desde`/`hasta` de la querystring (formato `YYYY-MM-DD`, el que
    manda un `<input type=date>`). Ante un valor vacío o inválido, cae al
    rango por defecto — un reporte nunca debe reventar por un filtro mal
    formado, solo mostrar el rango que sí pudo entender."""
    desde_defecto, hasta_defecto = rango_por_defecto()
    desde = _parsear_fecha(request.GET.get("desde")) or desde_defecto
    hasta = _parsear_fecha(request.GET.get("hasta")) or hasta_defecto
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _parsear_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def fondo_bloqueado_para(usuario):
    """Si el usuario es responsable_fondo (y no superusuario), devuelve su
    único `Fondo` — los reportes que filtran por fondo no le dejan elegir
    otro, igual que ya hace `GastoForm` al registrar. Para los demás roles
    devuelve None (pueden ver cualquier fondo o todos a la vez)."""
    if usuario.is_superuser:
        return None
    perfil = getattr(usuario, "perfilusuario", None)
    if perfil and perfil.rol == "responsable_fondo" and perfil.fondo_id:
        return perfil.fondo
    return None


# --- Reporte: ingresos por estudiante/sección/grado -------------------------

def ingresos_por_estudiante(desde, hasta, grado=None, seccion=None, solo_verificados=True):
    qs = Aporte.objects.filter(
        inscripcion__isnull=False, fecha_pago__gte=desde, fecha_pago__lte=hasta,
    )
    if solo_verificados:
        qs = qs.filter(estado=Aporte.Estado.VERIFICADO)
    else:
        qs = qs.exclude(estado=Aporte.Estado.ANULADO)
    if grado:
        qs = qs.filter(inscripcion__seccion__grado=grado)
    if seccion:
        qs = qs.filter(inscripcion__seccion=seccion)

    filas = (
        qs.values(
            "inscripcion__estudiante_id",
            "inscripcion__estudiante__nombres",
            "inscripcion__estudiante__apellidos",
            "inscripcion__estudiante__cedula_escolar",
            "inscripcion__seccion__nombre",
            "inscripcion__seccion__grado__nombre",
        )
        .annotate(total_ves=Sum("monto_ves"), total_usd=Sum("monto_usd"), cantidad=Count("id"))
        .order_by("inscripcion__seccion__grado__nombre", "inscripcion__seccion__nombre", "inscripcion__estudiante__apellidos")
    )
    totales = qs.aggregate(total_ves=Sum("monto_ves"), total_usd=Sum("monto_usd"), cantidad=Count("id"))
    return list(filas), totales


# --- Reporte: gastos por categoría/producto ----------------------------------

def gastos_por_categoria_producto(desde, hasta, fondo=None, categoria=None, producto=None):
    qs = DetalleGasto.objects.filter(
        gasto__estado=Gasto.Estado.APROBADO, gasto__fecha__gte=desde, gasto__fecha__lte=hasta,
    )
    if fondo:
        qs = qs.filter(gasto__fondo=fondo)
    if categoria:
        qs = qs.filter(producto__categoria=categoria)
    if producto:
        qs = qs.filter(producto=producto)

    filas = (
        qs.values(
            "producto__categoria_id",
            "producto__categoria__nombre",
            "producto__id",
            "producto__nombre",
        )
        .annotate(
            total_ves=Sum("subtotal_ves"), total_usd=Sum("subtotal_usd"), cantidad=Sum("cantidad"),
        )
        .order_by("producto__categoria__nombre", "producto__nombre")
    )
    # Renglones sin producto (solo descripción libre) quedan agrupados aparte.
    for fila in filas:
        if fila["producto__categoria__nombre"] is None:
            fila["producto__categoria__nombre"] = "Sin categoría / sin producto"
            fila["producto__nombre"] = fila["producto__nombre"] or "(descripción libre)"

    totales = qs.aggregate(total_ves=Sum("subtotal_ves"), total_usd=Sum("subtotal_usd"))
    return list(filas), totales


# --- Reporte: balance por fondo + evolución mensual --------------------------

def balance_por_fondo(fondos=None):
    """Saldo actual (acumulado, D-22) de cada fondo — o de los pasados en
    `fondos`, o de todos si no se filtra."""
    qs = fondos if fondos is not None else Fondo.objects.all()
    filas = []
    for fondo in qs:
        ves, usd = saldo_fondo(fondo)
        filas.append({"fondo": fondo, "saldo_ves": ves, "saldo_usd": usd})
    return filas


def evolucion_mensual(desde, hasta, fondo=None):
    """Ingresos verificados y gastos aprobados por mes, dentro de
    [desde, hasta], para el gráfico del tablero de balance. Devuelve una
    lista ordenada de dicts: {mes, ingresos_ves, gastos_ves, ingresos_usd, gastos_usd}."""
    aportes = Aporte.objects.filter(
        estado=Aporte.Estado.VERIFICADO, fecha_pago__gte=desde, fecha_pago__lte=hasta,
    )
    gastos = Gasto.objects.filter(
        estado=Gasto.Estado.APROBADO, fecha__gte=desde, fecha__lte=hasta,
    )
    if fondo:
        aportes = aportes.filter(fondo=fondo)
        gastos = gastos.filter(fondo=fondo)

    por_mes_ingresos = {
        fila["mes"]: fila
        for fila in aportes.annotate(mes=TruncMonth("fecha_pago"))
        .values("mes")
        .annotate(ves=Sum("monto_ves"), usd=Sum("monto_usd"))
    }
    por_mes_gastos = {
        fila["mes"]: fila
        for fila in gastos.annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(ves=Sum("monto_ves"), usd=Sum("monto_usd"))
    }

    meses = sorted(set(por_mes_ingresos) | set(por_mes_gastos))
    resultado = []
    for mes in meses:
        ingreso = por_mes_ingresos.get(mes, {})
        gasto = por_mes_gastos.get(mes, {})
        resultado.append({
            "mes": mes,
            "ingresos_ves": ingreso.get("ves") or CERO,
            "gastos_ves": gasto.get("ves") or CERO,
            "ingresos_usd": ingreso.get("usd") or CERO,
            "gastos_usd": gasto.get("usd") or CERO,
        })
    return resultado


# --- Relación de gastos institucionales (PDF) --------------------------------

def ingresos_por_concepto(desde, hasta, fondo=None):
    """Ingresos verificados agrupados por concepto (o `concepto_libre` cuando
    no viene del catálogo), para la tabla "Disponibilidad e Ingresos" del PDF."""
    qs = Aporte.objects.filter(estado=Aporte.Estado.VERIFICADO, fecha_pago__gte=desde, fecha_pago__lte=hasta)
    if fondo:
        qs = qs.filter(fondo=fondo)
    filas = (
        qs.annotate(etiqueta=Coalesce("concepto__nombre", "concepto_libre"))
        .values("etiqueta")
        .annotate(total_ves=Sum("monto_ves"))
        .order_by("etiqueta")
    )
    total = qs.aggregate(total_ves=Sum("monto_ves"))["total_ves"] or CERO
    return list(filas), total


def gastos_por_fondo_desglose(desde, hasta, fondo=None):
    """Gastos aprobados agrupados por fondo y, dentro de cada fondo, por
    producto (o descripción libre) — una columna por fondo en el PDF.
    Devuelve un dict ordenado {nombre_fondo: [(etiqueta, total_ves), ...]}."""
    qs = DetalleGasto.objects.filter(
        gasto__estado=Gasto.Estado.APROBADO, gasto__fecha__gte=desde, gasto__fecha__lte=hasta,
    )
    if fondo:
        qs = qs.filter(gasto__fondo=fondo)
    filas = (
        qs.annotate(etiqueta=Coalesce("producto__nombre", "descripcion"))
        .values("gasto__fondo__nombre", "etiqueta")
        .annotate(total_ves=Sum("subtotal_ves"))
        .order_by("gasto__fondo__nombre", "etiqueta")
    )
    por_fondo = {}
    for fila in filas:
        nombre = fila["gasto__fondo__nombre"]
        por_fondo.setdefault(nombre, []).append((fila["etiqueta"], fila["total_ves"] or CERO))
    return por_fondo


# --- Reporte: estado de cuenta por estudiante --------------------------------

def buscar_estudiantes(q):
    from academico.models import Estudiante

    if not q:
        return Estudiante.objects.none()
    return Estudiante.objects.filter(
        Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(cedula_escolar__icontains=q),
    ).order_by("apellidos", "nombres")[:20]


def estado_cuenta(estudiante):
    aportes = (
        Aporte.objects.filter(inscripcion__estudiante=estudiante)
        .exclude(estado=Aporte.Estado.ANULADO)
        .select_related("concepto", "inscripcion__periodo", "inscripcion__seccion")
        .order_by("-fecha_pago")
    )
    total_verificado = aportes.filter(estado=Aporte.Estado.VERIFICADO).aggregate(
        ves=Sum("monto_ves"), usd=Sum("monto_usd"),
    )
    return aportes, total_verificado
