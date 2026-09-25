"""Generación del PDF "Relación de gastos institucionales" (Fase 6).

Reproduce el formato que ya usaba la institución en papel (pedido explícito
de Darwin, con una foto de ejemplo): encabezado oficial, tabla de
"Disponibilidad e Ingresos" y el desglose de egresos en una columna por
fondo. Los montos se formatean en estilo `1,234.56` (coma de miles, punto
decimal) a propósito, IGUAL que el documento de ejemplo — es distinto del
formato es-VE (`1.234,56`) que usa el resto de la aplicación, porque aquí
el objetivo es replicar el documento tal cual lo conocía la institución,
no la convención interna de Edumia.
"""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MAX_COLUMNAS_POR_FILA = 3


def _fmt(valor):
    if valor is None:
        valor = Decimal("0")
    return f"{valor:,.2f}"


def _en_grupos(lista, tamano):
    for i in range(0, len(lista), tamano):
        yield lista[i:i + tamano]


def _estilos():
    estilos = getSampleStyleSheet()
    centrado = ParagraphStyle("centrado", parent=estilos["Normal"], alignment=TA_CENTER)
    titulo_estilo = ParagraphStyle("titulo_reporte", parent=estilos["Heading2"], alignment=TA_CENTER)
    return estilos, centrado, titulo_estilo


def _encabezado_institucional(institucion, ancho_util, centrado):
    """Bloque común a todos los PDF de reportes: escudo/nombre de la
    institución. Devuelve la lista de flowables lista para agregar al
    documento (con o sin logo, según exista `static/img/logo.png`)."""
    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo.png"
    textos = [
        Paragraph("República Bolivariana de Venezuela", centrado),
        Paragraph("Ministerio del Poder Popular para la Educación", centrado),
        Paragraph(f"<b>{institucion.nombre}</b>", centrado),
    ]
    if logo_path.exists():
        logo = Image(str(logo_path), width=1.8 * cm, height=1.8 * cm)
        tabla_logo = Table([[logo, textos]], colWidths=[2.2 * cm, ancho_util - 2.2 * cm])
        tabla_logo.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ]))
        return [tabla_logo]
    return textos


def _documento_base(titulo_pdf):
    buffer = BytesIO()
    margen = 1.5 * cm
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=margen, bottomMargin=margen, leftMargin=margen, rightMargin=margen,
        title=titulo_pdf,
    )
    return buffer, doc


def construir_tabla_pdf(institucion, periodo, titulo, desde, hasta, encabezados, filas, fila_total=None, anchos=None):
    """PDF genérico de una sola tabla, con el mismo encabezado institucional
    que `construir_relacion_gastos_pdf`. Usado por los reportes de Ingresos
    por estudiante y Gastos por categoría/producto — cualquier reporte
    tabular nuevo puede reutilizar esta misma función."""
    buffer, doc = _documento_base(titulo)
    ancho_util = doc.width
    estilos, centrado, titulo_estilo = _estilos()

    elementos = list(_encabezado_institucional(institucion, ancho_util, centrado))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph(titulo.upper(), titulo_estilo))
    if periodo:
        elementos.append(Paragraph(f"Año Escolar: {periodo.nombre}", centrado))
    elementos.append(Paragraph(f"Período de referencia: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}", centrado))
    elementos.append(Spacer(1, 0.5 * cm))

    datos = [encabezados] + [list(fila) for fila in filas]
    if fila_total:
        datos.append(list(fila_total))
    if anchos is None:
        anchos = [ancho_util / len(encabezados)] * len(encabezados)

    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#15467e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if fila_total:
        estilo.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
        estilo.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9ecef")))
    tabla.setStyle(TableStyle(estilo))
    elementos.append(tabla)

    doc.build(elementos)
    buffer.seek(0)
    return buffer


def construir_balance_pdf(institucion, periodo, desde, hasta, saldos, serie_mensual):
    """PDF del Balance por fondo: saldo actual de cada fondo + tabla de
    evolución mensual (los mismos datos que alimentan el gráfico en
    pantalla, aquí en forma de tabla para que se pueda imprimir)."""
    buffer, doc = _documento_base("Balance por fondo")
    ancho_util = doc.width
    estilos, centrado, titulo_estilo = _estilos()

    elementos = list(_encabezado_institucional(institucion, ancho_util, centrado))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph("BALANCE POR FONDO", titulo_estilo))
    if periodo:
        elementos.append(Paragraph(f"Año Escolar: {periodo.nombre}", centrado))
    elementos.append(Paragraph(f"Período de referencia: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}", centrado))
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph("Saldo actual (acumulado)", estilos["Heading4"]))
    datos_saldos = [["Fondo", "Saldo Bs.", "Saldo $"]]
    for fila in saldos:
        datos_saldos.append([str(fila["fondo"]), _fmt(fila["saldo_ves"]), _fmt(fila["saldo_usd"])])
    tabla_saldos = Table(datos_saldos, colWidths=[ancho_util - 8 * cm, 4 * cm, 4 * cm])
    tabla_saldos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#15467e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elementos.append(tabla_saldos)
    elementos.append(Spacer(1, 0.6 * cm))

    elementos.append(Paragraph("Evolución mensual", estilos["Heading4"]))
    if serie_mensual:
        datos_mensual = [["Mes", "Ingresos Bs.", "Gastos Bs.", "Ingresos $", "Gastos $"]]
        for fila in serie_mensual:
            datos_mensual.append([
                fila["mes"].strftime("%m/%Y"),
                _fmt(fila["ingresos_ves"]), _fmt(fila["gastos_ves"]),
                _fmt(fila["ingresos_usd"]), _fmt(fila["gastos_usd"]),
            ])
        ancho_col = ancho_util / 5
        tabla_mensual = Table(datos_mensual, colWidths=[ancho_col] * 5, repeatRows=1)
        tabla_mensual.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1aa18a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ]))
        elementos.append(tabla_mensual)
    else:
        elementos.append(Paragraph("No hay movimientos en este rango.", estilos["Normal"]))

    doc.build(elementos)
    buffer.seek(0)
    return buffer


def construir_relacion_gastos_pdf(institucion, periodo, desde, hasta, ingresos_filas, total_ingresos, egresos_por_fondo):
    """Devuelve un `BytesIO` con el PDF ya armado, listo para `HttpResponse`."""
    buffer, doc = _documento_base("Relación de gastos institucionales")
    ancho_util = doc.width

    estilos, centrado, titulo_estilo = _estilos()

    elementos = list(_encabezado_institucional(institucion, ancho_util, centrado))

    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph("RELACIÓN DE GASTOS INSTITUCIONALES", titulo_estilo))
    if periodo:
        elementos.append(Paragraph(f"Año Escolar: {periodo.nombre}", centrado))
    elementos.append(Paragraph(f"Período de referencia: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}", centrado))
    elementos.append(Spacer(1, 0.5 * cm))

    # --- Disponibilidad e ingresos ---------------------------------------
    elementos.append(Paragraph("Disponibilidad e Ingresos", estilos["Heading4"]))
    datos_ingresos = [["Concepto", "Monto (Bs.)"]]
    for fila in ingresos_filas:
        datos_ingresos.append([fila["etiqueta"] or "(sin concepto)", _fmt(fila["total_ves"])])
    datos_ingresos.append(["TOTAL INGRESOS", _fmt(total_ingresos)])
    tabla_ingresos = Table(datos_ingresos, colWidths=[ancho_util - 4 * cm, 4 * cm])
    tabla_ingresos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#15467e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9ecef")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elementos.append(tabla_ingresos)
    elementos.append(Spacer(1, 0.6 * cm))

    # --- Desglose de egresos, una columna por fondo -----------------------
    elementos.append(Paragraph("Desglose de Egresos (Gastos)", estilos["Heading4"]))
    if egresos_por_fondo:
        nombres_fondo = list(egresos_por_fondo.keys())
        for grupo in _en_grupos(nombres_fondo, MAX_COLUMNAS_POR_FILA):
            ancho_columna = ancho_util / len(grupo)
            tablas_fondo = []
            for nombre_fondo in grupo:
                filas_fondo = egresos_por_fondo[nombre_fondo]
                subtotal = sum((monto for _, monto in filas_fondo), Decimal("0"))
                datos = [[f"Egresos {nombre_fondo}", ""], ["Descripción del Gasto", "Monto (Bs.)"]]
                for etiqueta, monto in filas_fondo:
                    datos.append([etiqueta or "(sin descripción)", _fmt(monto)])
                datos.append(["Subtotal", _fmt(subtotal)])
                tabla = Table(datos, colWidths=[ancho_columna * 0.62, ancho_columna * 0.38])
                tabla.setStyle(TableStyle([
                    ("SPAN", (0, 0), (-1, 0)),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1aa18a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#dee2e6")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9ecef")),
                    ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))
                tablas_fondo.append(tabla)
            fila_columnas = Table([tablas_fondo], colWidths=[ancho_columna] * len(grupo))
            fila_columnas.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            elementos.append(fila_columnas)
            elementos.append(Spacer(1, 0.3 * cm))
    else:
        elementos.append(Paragraph("No hay gastos aprobados en este rango.", estilos["Normal"]))

    doc.build(elementos)
    buffer.seek(0)
    return buffer
