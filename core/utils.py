"""Normalización de datos que se repite en varias apps (cédulas, teléfonos).

Un solo lugar para esta lógica: si cambia la regla, cambia aquí y no en
cada modelo o formulario que la use.
"""

import re


def normalizar_cedula(valor: str | None) -> str | None:
    """Quita puntos, guiones y espacios; deja el prefijo (V/E/J) en mayúscula.

    'V-12.345.678' -> 'V12345678'
    '12345678'     -> '12345678'
    None o ''      -> None (para que los campos nullable queden NULL, no '')
    """
    if not valor:
        return None
    limpio = re.sub(r"[.\-\s]", "", valor).upper()
    return limpio or None


def normalizar_telefono(valor: str | None) -> str:
    """Deja solo dígitos. No fuerza longitud aquí: cada modelo valida la suya."""
    if not valor:
        return ""
    return re.sub(r"\D", "", valor)
