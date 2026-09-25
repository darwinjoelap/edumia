"""Cálculo del saldo por fondo (docs/MODELOS_gastos.md).

Los dos saldos (Bs. y USD) no se convierten entre sí: cada transacción ya
trae su tasa congelada, y sumar en cada moneda por separado hace que
siempre cuadre con el papel.
"""

from decimal import Decimal


def saldo_fondo(fondo, hasta=None):
    """(saldo_ves, saldo_usd) de `fondo`:

    saldo = saldo_inicial + Σ aportes verificados − Σ gastos aprobados
            + Σ transferencias entrantes registradas − Σ transferencias salientes registradas

    `saldo_inicial_ves`/`saldo_inicial_usd` (Fase 8, D-32) es el punto de partida — lo que el
    fondo ya tenía antes de usar Edumia — y se suma siempre, sin importar `hasta`: no es un
    movimiento con fecha, es el arranque.

    Las transferencias entre fondos (Fase 8, D-36) mueven dinero de un fondo a otro sin que
    sea un ingreso ni un gasto real — se sacan aparte, no como `Aporte`/`Gasto`.

    `hasta` (opcional) filtra todas las sumas a `fecha <= hasta` / `fecha_pago <= hasta`.
    """
    from django.db.models import Sum

    from ingresos.models import Aporte

    from .models import Gasto, TransferenciaFondo

    aportes = Aporte.objects.filter(fondo=fondo, estado=Aporte.Estado.VERIFICADO)
    gastos = Gasto.objects.filter(fondo=fondo, estado=Gasto.Estado.APROBADO)
    entradas = TransferenciaFondo.objects.filter(
        fondo_destino=fondo, estado=TransferenciaFondo.Estado.REGISTRADA,
    )
    salidas = TransferenciaFondo.objects.filter(
        fondo_origen=fondo, estado=TransferenciaFondo.Estado.REGISTRADA,
    )
    if hasta is not None:
        aportes = aportes.filter(fecha_pago__lte=hasta)
        gastos = gastos.filter(fecha__lte=hasta)
        entradas = entradas.filter(fecha__lte=hasta)
        salidas = salidas.filter(fecha__lte=hasta)

    ingresos = aportes.aggregate(ves=Sum("monto_ves"), usd=Sum("monto_usd"))
    egresos = gastos.aggregate(ves=Sum("monto_ves"), usd=Sum("monto_usd"))
    entradas_ves = entradas.filter(moneda="VES").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    entradas_usd = entradas.filter(moneda="USD").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    salidas_ves = salidas.filter(moneda="VES").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    salidas_usd = salidas.filter(moneda="USD").aggregate(t=Sum("monto"))["t"] or Decimal("0")

    saldo_ves = (
        fondo.saldo_inicial_ves + (ingresos["ves"] or Decimal("0")) - (egresos["ves"] or Decimal("0"))
        + entradas_ves - salidas_ves
    )
    saldo_usd = (
        fondo.saldo_inicial_usd + (ingresos["usd"] or Decimal("0")) - (egresos["usd"] or Decimal("0"))
        + entradas_usd - salidas_usd
    )
    return saldo_ves, saldo_usd
