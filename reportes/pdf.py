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


def construir_relacion_gastos_pdf(institucion, periodo, desde, hasta, ingresos_filas, total_ingresos, egresos_por_fondo):
    """Devuelve un `BytesIO` con el PDF ya armado, listo para `HttpResponse`."""
    buffer = BytesIO()
    margen = 1.5 * cm
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=margen, bottomMargin=margen, leftMargin=margen, rightMargin=margen,
        title="Relación de gastos institucionales",
    )
    ancho_util = doc.width

    estilos = getSampleStyleSheet()
    centrado = ParagraphStyle("centrado", parent=estilos["Normal"], alignment=TA_CENTER)
    titulo_estilo = ParagraphStyle("titulo_relacion", parent=estilos["Heading2"], alignment=TA_CENTER)

    elementos = []

    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo.png"
    textos_encabezado = [
        Paragraph("República Bolivariana de Venezuela", centrado),
        Paragraph("Ministerio del Poder Popular para la Educación", centrado),
        Paragraph(f"<b>{institucion.nombre}</b>", centrado),
    ]
    if logo_path.exists():
        logo = Image(str(logo_path), width=1.8 * cm, height=1.8 * cm)
        tabla_logo = Table([[logo, textos_encabezado]], colWidths=[2.2 * cm, ancho_util - 2.2 * cm])
        tabla_logo.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ]))
        elementos.append(tabla_logo)
    else:
        elementos.extend(textos_encabezado)

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
