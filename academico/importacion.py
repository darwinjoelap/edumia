"""Lectura y validación de archivos de alta de estudiantes (Excel/CSV).

Formato esperado, dos variantes:
1. Con fila de encabezado: nombres, apellidos, fecha_nacimiento, sexo,
   cedula_escolar (opcional). El orden de las columnas no importa,
   mayúsculas/minúsculas tampoco.
2. Sin encabezado (el archivo empieza directo con datos): se asume el
   orden fijo nombres, apellidos, fecha_nacimiento, sexo, cedula_escolar.
   Se detecta automáticamente comparando la primera fila: si no contiene
   literalmente las palabras "nombres" y "apellidos", se trata como datos.

La validación reutiliza EstudianteRapidoForm (el mismo form de la alta
rápida manual), así que las reglas de "qué es obligatorio" y la unicidad
condicional de cedula_escolar quedan en un solo lugar.
"""
import csv
import io
from datetime import date, datetime

import openpyxl

from .forms import EstudianteRapidoForm

FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y")
COLUMNAS_OBLIGATORIAS = ("nombres", "apellidos", "fecha_nacimiento", "sexo")

# Si el archivo no trae fila de encabezado, se asume este orden de columnas.
COLUMNAS_POSICIONALES = ("nombres", "apellidos", "fecha_nacimiento", "sexo", "cedula_escolar")


class FilaImportada:
    """Una fila del archivo que no pudo importarse, con su motivo."""

    def __init__(self, numero, errores):
        self.numero = numero
        self.errores = errores


def _normalizar_encabezado(valor):
    return (valor or "").strip().lower()


def _parece_encabezado(fila_normalizada):
    """True si la primera fila trae nombres de columna reconocibles y no
    son ya datos de un estudiante (ej: no confundir "nombres" de columna
    con un nombre de pila cualquiera)."""
    return "nombres" in fila_normalizada and "apellidos" in fila_normalizada


def _parsear_fecha(valor):
    if valor in (None, ""):
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return texto  # no se pudo interpretar; el form lo marcará como inválido


def _parsear_sexo(valor):
    texto = str(valor).strip().upper() if valor else ""
    if texto in ("M", "MASCULINO"):
        return "M"
    if texto in ("F", "FEMENINO"):
        return "F"
    return texto  # se deja tal cual para que el form marque el error


def _leer_filas_xlsx(archivo):
    libro = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
    hoja = libro.active
    filas_todas = [
        fila for fila in hoja.iter_rows(values_only=True)
        if fila and any(c not in (None, "") for c in fila)
    ]
    if not filas_todas:
        return

    primera_normalizada = [_normalizar_encabezado(c) for c in filas_todas[0]]
    if _parece_encabezado(primera_normalizada):
        encabezado = primera_normalizada
        filas_datos = filas_todas[1:]
        numero_inicial = 2
    else:
        encabezado = list(COLUMNAS_POSICIONALES)
        filas_datos = filas_todas
        numero_inicial = 1

    for offset, fila in enumerate(filas_datos):
        yield numero_inicial + offset, dict(zip(encabezado, fila))


def _leer_filas_csv(archivo):
    contenido = archivo.read()
    texto = None
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            texto = contenido.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        texto = contenido.decode("utf-8", errors="replace")

    filas_todas = [
        fila for fila in csv.reader(io.StringIO(texto))
        if any((c or "").strip() for c in fila)
    ]
    if not filas_todas:
        return

    primera_normalizada = [_normalizar_encabezado(c) for c in filas_todas[0]]
    if _parece_encabezado(primera_normalizada):
        encabezado = primera_normalizada
        filas_datos = filas_todas[1:]
        numero_inicial = 2
    else:
        encabezado = list(COLUMNAS_POSICIONALES)
        filas_datos = filas_todas
        numero_inicial = 1

    for offset, fila in enumerate(filas_datos):
        yield numero_inicial + offset, dict(zip(encabezado, fila))


def leer_archivo(archivo):
    nombre = archivo.name.lower()
    if nombre.endswith(".xlsx"):
        return list(_leer_filas_xlsx(archivo))
    return list(_leer_filas_csv(archivo))


def validar_archivo(archivo):
    """Devuelve (filas_validas, filas_error, columnas_faltantes).

    filas_validas: lista de dicts listos para crear Estudiante + Inscripcion
    (fecha_nacimiento como texto ISO, para poder guardarse en la sesión).
    filas_error: lista de FilaImportada, con su número de fila y motivo(s).
    columnas_faltantes: nombres de columnas obligatorias que no vinieron en
    el archivo; si esta lista no está vacía, las otras dos vienen vacías.
    """
    filas_crudas = leer_archivo(archivo)

    encabezados_presentes = set(filas_crudas[0][1].keys()) if filas_crudas else set()
    columnas_faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in encabezados_presentes]
    if columnas_faltantes:
        return [], [], columnas_faltantes

    filas_validas = []
    filas_error = []
    cedulas_vistas = set()

    for numero, datos in filas_crudas:
        fecha_iso = _parsear_fecha(datos.get("fecha_nacimiento"))
        form_data = {
            "nombres": (datos.get("nombres") or "").strip(),
            "apellidos": (datos.get("apellidos") or "").strip(),
            "fecha_nacimiento": fecha_iso,
            "sexo": _parsear_sexo(datos.get("sexo")),
            "cedula_escolar": str(datos.get("cedula_escolar") or "").strip(),
        }
        form = EstudianteRapidoForm(data=form_data)
        if not form.is_valid():
            if form.fila_vacia():
                continue  # fila realmente vacía (columnas extra vacías), se ignora
            mensajes = []
            for campo, errores_campo in form.errors.items():
                for error in errores_campo:
                    mensajes.append(error if campo == "__all__" else f"{campo}: {error}")
            filas_error.append(FilaImportada(numero, mensajes or ["Datos inválidos."]))
            continue

        if form.fila_vacia():
            continue

        cedula = form.cleaned_data.get("cedula_escolar")
        if cedula and cedula in cedulas_vistas:
            filas_error.append(FilaImportada(numero, ["Cédula repetida en el mismo archivo."]))
            continue
        if cedula:
            cedulas_vistas.add(cedula)

        cleaned = form.cleaned_data
        filas_validas.append({
            "numero": numero,
            "nombres": cleaned["nombres"],
            "apellidos": cleaned["apellidos"],
            "fecha_nacimiento": cleaned["fecha_nacimiento"].isoformat(),
            "sexo": cleaned["sexo"],
            "cedula_escolar": cleaned.get("cedula_escolar") or "",
        })

    return filas_validas, filas_error, columnas_faltantes
