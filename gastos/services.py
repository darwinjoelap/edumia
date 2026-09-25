"""Cálculo del saldo por fondo (docs/MODELOS_gastos.md).

Los dos saldos (Bs. y USD) no se convierten entre sí: cada transacción ya
trae su tasa congelada, y sumar en cada moneda por separado hace que
siempre cuadre con el papel.
"""

from decimal import Decimal


def saldo_fondo(fondo, hasta=None):
    """(saldo_ves, saldo_usd) de `fondo`:

    saldo = Σ aportes verificados (monto_ves/monto_usd) − Σ gastos aprobados (monto_ves/monto_usd)

    `hasta` (opcional) filtra ambas sumas a `fecha <= hasta` / `fecha_pago <= hasta`.
    """
    from django.db.models import Sum

    from ingresos.models import Aporte

    from .models import Gasto

    aportes = Aporte.objects.filter(fondo=fondo, estado=Aporte.Estado.VERIFICADO)
    gastos = Gasto.objects.filter(fondo=fondo, estado=Gasto.Estado.APROBADO)
    if hasta is not None:
        aportes = aportes.filter(fecha_pago__lte=hasta)
        gastos = gastos.filter(fecha__lte=hasta)

    ingresos = aportes.aggregate(ves=Sum("monto_ves"), usd=Sum("monto_usd"))
    egresos = gastos.aggregate(ves=Sum("monto_ves"), usd=Sum("monto_usd"))

    saldo_ves = (ingresos["ves"] or Decimal("0")) - (egresos["ves"] or Decimal("0"))
    saldo_usd = (ingresos["usd"] or Decimal("0")) - (egresos["usd"] or Decimal("0"))
    return saldo_ves, saldo_usd
