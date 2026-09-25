from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from academico.models import Estudiante
from core.mixins import requiere_rol
from core.models import Institucion, PeriodoEscolar
from gastos.models import Fondo

from . import pdf, services
from .forms import BuscarEstudianteForm, FiltroBalanceForm, FiltroGastosForm, FiltroIngresosForm

# Roles que ven los reportes financieros: los mismos que ven el balance en
# el dashboard (core.views.ROLES_FINANZAS). El docente no entra aquí — si
# hace falta un reporte acotado a su propia sección más adelante, se agrega
# aparte, sin abrir todo el módulo.
ROLES_REPORTES = ("administrador", "responsable_fondo", "director", "auditor")


def _exportar_xlsx(nombre_archivo, encabezados, filas):
    """Construye un .xlsx en memoria a partir de una lista de encabezados y
    una lista de filas (cada fila, una lista de valores en el mismo orden).
    Usado por los cuatro reportes para no repetir la misma mecánica de
    openpyxl cuatro veces."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte"
    hoja.append(encabezados)
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for fila in filas:
        hoja.append(fila)
    for columna in hoja.columns:
        largo = max((len(str(c.value)) for c in columna if c.value is not None), default=10)
        hoja.column_dimensions[columna[0].column_letter].width = min(largo + 2, 40)

    respuesta = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    libro.save(respuesta)
    return respuesta


def _exportar_pdf(buffer, nombre_archivo):
    respuesta = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


def _institucion_y_periodo():
    return Institucion.obtener(), PeriodoEscolar.objects.filter(activo=True).first()


@login_required
@requiere_rol(*ROLES_REPORTES)
def inicio(request):
    return render(request, "reportes/inicio.html")


@login_required
@requiere_rol(*ROLES_REPORTES)
def ingresos_estudiantes(request):
    form = FiltroIngresosForm(request.GET or None)
    desde, hasta = services.parsear_rango(request)
    grado = seccion = None
    solo_verificados = True
    if form.is_valid():
        desde = form.cleaned_data["desde"] or desde
        hasta = form.cleaned_data["hasta"] or hasta
        grado = form.cleaned_data["grado"]
        seccion = form.cleaned_data["seccion"]
        solo_verificados = form.cleaned_data["solo_verificados"]

    filas, totales = services.ingresos_por_estudiante(desde, hasta, grado, seccion, solo_verificados)

    if request.GET.get("formato") == "xlsx":
        encabezados = ["Estudiante", "Cédula escolar", "Sección", "Grado", "Total Bs.", "Total $", "# aportes"]
        cuerpo = [
            [
                f"{f['inscripcion__estudiante__apellidos']} {f['inscripcion__estudiante__nombres']}",
                f["inscripcion__estudiante__cedula_escolar"] or "",
                f["inscripcion__seccion__nombre"],
                f["inscripcion__seccion__grado__nombre"],
                float(f["total_ves"] or 0),
                float(f["total_usd"] or 0),
                f["cantidad"],
            ]
            for f in filas
        ]
        return _exportar_xlsx(f"ingresos_{desde}_{hasta}.xlsx", encabezados, cuerpo)

    if request.GET.get("formato") == "pdf":
        institucion, periodo = _institucion_y_periodo()
        encabezados = ["Estudiante", "Cédula", "Grado", "Sección", "Total Bs.", "Total $", "# aportes"]
        cuerpo = [
            [
                f"{f['inscripcion__estudiante__apellidos']} {f['inscripcion__estudiante__nombres']}",
                f["inscripcion__estudiante__cedula_escolar"] or "—",
                f["inscripcion__seccion__grado__nombre"],
                f["inscripcion__seccion__nombre"],
                pdf._fmt(f["total_ves"]),
                pdf._fmt(f["total_usd"]),
                f["cantidad"],
            ]
            for f in filas
        ]
        fila_total = ["TOTAL", "", "", "", pdf._fmt(totales["total_ves"]), pdf._fmt(totales["total_usd"]), totales["cantidad"] or 0]
        buffer = pdf.construir_tabla_pdf(
            institucion, periodo, "Ingresos por estudiante", desde, hasta, encabezados, cuerpo, fila_total,
        )
        return _exportar_pdf(buffer, f"ingresos_{desde}_{hasta}.pdf")

    return render(request, "reportes/ingresos_estudiantes.html", {
        "form": form, "filas": filas, "totales": totales, "desde": desde, "hasta": hasta,
    })


@login_required
@requiere_rol(*ROLES_REPORTES)
def gastos_categorias(request):
    form = FiltroGastosForm(request.GET or None, usuario=request.user)
    desde, hasta = services.parsear_rango(request)
    fondo = categoria = producto = None
    fondo_fijo = services.fondo_bloqueado_para(request.user)
    if form.is_valid():
        desde = form.cleaned_data["desde"] or desde
        hasta = form.cleaned_data["hasta"] or hasta
        fondo = fondo_fijo or form.cleaned_data["fondo"]
        categoria = form.cleaned_data["categoria"]
        producto = form.cleaned_data["producto"]
    elif fondo_fijo:
        fondo = fondo_fijo

    filas, totales = services.gastos_por_categoria_producto(desde, hasta, fondo, categoria, producto)

    if request.GET.get("formato") == "xlsx":
        encabezados = ["Categoría", "Producto", "Cantidad", "Total Bs.", "Total $"]
        cuerpo = [
            [
                f["producto__categoria__nombre"] or "Sin categoría",
                f["producto__nombre"] or "(descripción libre)",
                float(f["cantidad"] or 0),
                float(f["total_ves"] or 0),
                float(f["total_usd"] or 0),
            ]
            for f in filas
        ]
        return _exportar_xlsx(f"gastos_{desde}_{hasta}.xlsx", encabezados, cuerpo)

    if request.GET.get("formato") == "pdf":
        institucion, periodo = _institucion_y_periodo()
        encabezados = ["Categoría", "Producto", "Cantidad", "Total Bs.", "Total $"]
        cuerpo = [
            [
                f["producto__categoria__nombre"] or "Sin categoría",
                f["producto__nombre"] or "(descripción libre)",
                str(f["cantidad"] or 0),
                pdf._fmt(f["total_ves"]),
                pdf._fmt(f["total_usd"]),
            ]
            for f in filas
        ]
        fila_total = ["TOTAL", "", "", pdf._fmt(totales["total_ves"]), pdf._fmt(totales["total_usd"])]
        buffer = pdf.construir_tabla_pdf(
            institucion, periodo, "Gastos por categoría y producto", desde, hasta, encabezados, cuerpo, fila_total,
        )
        return _exportar_pdf(buffer, f"gastos_{desde}_{hasta}.pdf")

    return render(request, "reportes/gastos_categorias.html", {
        "form": form, "filas": filas, "totales": totales, "desde": desde, "hasta": hasta,
    })


@login_required
@requiere_rol(*ROLES_REPORTES)
def balance(request):
    form = FiltroBalanceForm(request.GET or None, usuario=request.user)
    desde, hasta = services.parsear_rango(request)
    fondo = None
    fondo_fijo = services.fondo_bloqueado_para(request.user)
    if form.is_valid():
        desde = form.cleaned_data["desde"] or desde
        hasta = form.cleaned_data["hasta"] or hasta
        fondo = fondo_fijo or form.cleaned_data["fondo"]
    elif fondo_fijo:
        fondo = fondo_fijo

    fondos_qs = Fondo.objects.filter(pk=fondo.pk) if fondo else None
    saldos = services.balance_por_fondo(fondos_qs)
    serie_mensual = services.evolucion_mensual(desde, hasta, fondo)

    if request.GET.get("formato") == "pdf":
        institucion, periodo = _institucion_y_periodo()
        buffer = pdf.construir_balance_pdf(institucion, periodo, desde, hasta, saldos, serie_mensual)
        return _exportar_pdf(buffer, f"balance_{desde}_{hasta}.pdf")

    return render(request, "reportes/balance.html", {
        "form": form, "saldos": saldos, "desde": desde, "hasta": hasta,
        "serie_mensual": serie_mensual,
        "serie_json": [
            {
                "mes": s["mes"].strftime("%Y-%m"),
                "ingresos_ves": float(s["ingresos_ves"]), "gastos_ves": float(s["gastos_ves"]),
                "ingresos_usd": float(s["ingresos_usd"]), "gastos_usd": float(s["gastos_usd"]),
            }
            for s in serie_mensual
        ],
    })


@login_required
@requiere_rol(*ROLES_REPORTES)
def relacion_gastos_pdf(request):
    """Relación de gastos institucionales en PDF: ingresos por concepto +
    egresos por fondo, con el formato en papel que ya usaba la institución
    (pedido explícito de Darwin, con una foto de ejemplo)."""
    form = FiltroBalanceForm(request.GET or None, usuario=request.user)
    desde, hasta = services.parsear_rango(request)
    fondo = None
    fondo_fijo = services.fondo_bloqueado_para(request.user)
    if form.is_valid():
        desde = form.cleaned_data["desde"] or desde
        hasta = form.cleaned_data["hasta"] or hasta
        fondo = fondo_fijo or form.cleaned_data["fondo"]
    elif fondo_fijo:
        fondo = fondo_fijo

    if request.GET.get("formato") != "pdf":
        return render(request, "reportes/relacion_gastos.html", {
            "form": form, "desde": desde, "hasta": hasta,
        })

    institucion = Institucion.obtener()
    periodo = PeriodoEscolar.objects.filter(activo=True).first()
    ingresos_filas, total_ingresos = services.ingresos_por_concepto(desde, hasta, fondo)
    egresos_por_fondo = services.gastos_por_fondo_desglose(desde, hasta, fondo)

    buffer = pdf.construir_relacion_gastos_pdf(
        institucion, periodo, desde, hasta, ingresos_filas, total_ingresos, egresos_por_fondo,
    )
    respuesta = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="relacion_gastos_{desde}_{hasta}.pdf"'
    return respuesta


@login_required
@requiere_rol(*ROLES_REPORTES)
def estudiante_cuenta(request):
    form = BuscarEstudianteForm(request.GET or None)
    q = request.GET.get("q", "").strip()
    resultados = services.buscar_estudiantes(q) if q else Estudiante.objects.none()

    estudiante = None
    aportes = totales = None
    estudiante_id = request.GET.get("estudiante")
    if estudiante_id:
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
        aportes, totales = services.estado_cuenta(estudiante)

    return render(request, "reportes/estudiante_cuenta.html", {
        "form": form, "q": q, "resultados": resultados,
        "estudiante": estudiante, "aportes": aportes, "totales": totales,
    })
