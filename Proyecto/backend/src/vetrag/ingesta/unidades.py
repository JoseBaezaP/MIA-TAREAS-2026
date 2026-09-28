"""Catálogo de unidades de medida, para distinguir unidades reales de errores del OCR.

El catálogo se arma combinando **prefijos con unidades base**, como en las tablas de unidades
SI (Tabla 1: unidades SI y derivadas; Tabla 2: prefijos; Tablas 3 y 4: unidades
anglosajonas). Así ``mg``, ``ng``, ``µg``, ``mmol``, ``mval``, ``kcal``… no se escriben una
por una.

Además tiene la tabla de **confusiones típicas del OCR** (``rn`` → ``m``, ``Ul`` → ``UI``,
la µ leída como ``llg``, ``IJg``…). Solo se corrige cuando el resultado es una unidad del
catálogo y lo leído no es ninguna unidad real; lo ambiguo (``mi/kg``, ``u/kg``) solo se
reporta.
"""

import re
from itertools import product

# --- Tabla 2: prefijos --------------------------------------------------------------------
# M (mega), k/K (kilo), h/H (hecto), da/D (deca), d (deci), c (centi), m (mili),
# µ/μ/u (micro: símbolo micro, letra griega mu y la "u" que se usa sin teclado griego),
# n (nano), p (pico), f (femto: no está en la tabla, pero aparece en el corpus: fmol) y sin
# prefijo.
PREFIJOS = ("M", "k", "K", "h", "H", "da", "D", "d", "c", "m", "µ", "μ", "u", "n", "p", "f", "")

# --- Tabla 1: unidades que aceptan prefijo ------------------------------------------------
BASES_CON_PREFIJO = (
    "g",  # gramo
    "mol",  # mol
    "M",  # molar
    "val",  # val (mval)
    "Eq", "eq",  # equivalente (mEq)
    "Osm", "osm", "osmol", "Osmol",  # osmol (mOsm, mosmol)
    "l", "L",  # litro
    "m",  # metro
    "s",  # segundo
    "Pa", "bar",  # presión
    "J", "cal",  # energía
    "kat",  # katal
    "Bq", "Ci",  # radiactividad
    "Gy", "rd",  # dosis absorbida
    "A", "V", "W", "Hz",  # electricidad y frecuencia
    "U", "UI", "IU",  # unidades (enzimáticas / internacionales): mUI/ml
    "Da",  # dalton (kDa)
)  # fmt: skip

# --- Tablas 1, 3 y 4: unidades sin prefijo, anglosajonas y clínicas -----------------------
SIN_PREFIJO = (
    "mmHg", "Torr", "atm", "°C", "°F", "K", "%", "‰", "ppm", "ppb", "ppt",
    "t", "D", "cc", "min", "h", "d", "día", "dia",
    # Anglosajonas (Tabla 3). Ojo: "gr" es grain (64.8 mg) en inglés, pero en español se usa
    # para "gramo". Es una unidad real, pero AMBIGUA: el agente debe advertirlo.
    "gr", "grain", "dr", "oz", "lb", "lbs", "pt", "qt", "gal", "gi", "minim",
    # Clínicas frecuentes
    "gota", "gotas", "gts", "tab", "comp", "UFC", "ufc",
    # Encontradas en el corpus completo (2026-09-27): abreviaturas en inglés y frecuencias
    "mcg",  # microgramo en textos en inglés (= µg)
    "gm", "grams", "unit", "units", "Units", "mmoles",
    "PNU",  # protein nitrogen units (extractos alergénicos)
    "vez", "veces",  # "3 veces/día"
    "lat", "rev",  # latidos/min, revoluciones/min
    "microl",  # microlitro escrito con letras
    "CFU", "AU", "EU",  # colony forming / arbitrary / endotoxin units
    "spz",  # espermatozoides/ml
    "gram", "Unit", "moles", "cells", "beats",
    "tomas", "horas", "litros",  # "3 tomas/día"
    "ui", "Ui",  # "UI" escrito en minúsculas, frecuente en textos en español
)  # fmt: skip

# Lo que puede ir después de la "/" en una dosis o concentración.
DENOMINADORES = (
    "kg",
    "lb",
    "l",
    "L",
    "dl",
    "dL",
    "ml",
    "mL",
    "m2",
    "m²",
    "h",
    "min",
    "día",
    "dia",
    "d",
)


def _unificar_micro(unidad: str) -> str:
    """Un solo símbolo para "micro": la letra griega μ y el símbolo µ se ven igual pero son
    caracteres distintos."""
    return unidad.replace("μ", "µ")


# Se respetan mayúsculas y minúsculas: "mA" (miliamperio) es real, "ma" (un "mg" mal leído)
# no; "M" (molar) no es "m" (metro).
UNIDADES_CONOCIDAS: frozenset[str] = frozenset(
    {_unificar_micro(p + b) for p, b in product(PREFIJOS, BASES_CON_PREFIJO)}
    | {_unificar_micro(u) for u in SIN_PREFIJO}
)
_UNIDADES_EN_MINUSCULAS = frozenset(u.lower() for u in UNIDADES_CONOCIDAS)


def es_unidad_conocida(unidad: str) -> bool:
    """``mval`` → ``True``; ``ma`` o ``1a`` (errores de OCR) → ``False``.

    Una unidad escrita **toda en mayúsculas** (``MG``, ``ML``, común en tablas) se acepta si
    existe en minúsculas.
    """
    unidad = _unificar_micro(unidad)
    if unidad in UNIDADES_CONOCIDAS:
        return True
    return len(unidad) > 1 and unidad.isupper() and unidad.lower() in _UNIDADES_EN_MINUSCULAS


# Cantidad + unidad + "/" + denominador, p. ej. "5 mg/kg", "0,5-1 1a/kg/h", "|10-20|µg/kg".
# La unidad puede empezar con "1" + letra porque así lee el OCR una "µ" (p. ej. "1a").
_DENOMINADORES_REGEX = "|".join(
    sorted((re.escape(d) for d in DENOMINADORES), key=len, reverse=True)
)
PATRON_UNIDAD_COMPUESTA = re.compile(
    rf"\d[\s|]*(?P<unidad>1[a-zA-Z]{{1,2}}|[A-Za-zµμ°%‰][A-Za-zµμ²]{{0,5}})"
    rf"/(?P<denominador>{_DENOMINADORES_REGEX})(?![A-Za-z])"
)

# Palabras que indican que una línea habla de una dosis.
_PATRON_CONTEXTO_DOSIS = re.compile(
    r"\b(IV|IM|SC|VO|PO|IO|CRI|bolo|bolus|dosis|dose|cada|q\d{1,2}h|infusi[oó]n|infusion)\b"
    r"|/(h|min)\b",
    re.IGNORECASE,
)


def tiene_contexto_de_dosis(linea: str) -> bool:
    """``True`` si la línea habla de una dosis (vía de administración, bolo, CRI, cada…)."""
    return bool(_PATRON_CONTEXTO_DOSIS.search(linea))


def buscar_unidades_desconocidas(texto: str) -> list[str]:
    """Fragmentos con una unidad compuesta que no está en el catálogo (posible error de OCR)."""
    sospechosas = []
    for coincidencia in PATRON_UNIDAD_COMPUESTA.finditer(texto):
        if not es_unidad_conocida(coincidencia.group("unidad")):
            inicio = max(coincidencia.start() - 30, 0)
            sospechosas.append(" ".join(texto[inicio : coincidencia.end() + 10].split()))
    return sospechosas


# --- Confusiones típicas del OCR -------------------------------------------------------------
# Lo leído → (lo real, regla). Cada entrada salió del reporte del corpus completo y se revisó en
# contexto: lo leído NO es una unidad real y la corrección SÍ está en el catálogo.
# No están a propósito: "pg" (real: picogramo), "1g" ("1 g/dl" es real), "ig", "rg", "mi", "u"
# (ambiguas: podrían ser mg, µg o ml) y "Jg"/"1Jg": en "(1Jg/ml)" no se sabe si el "1" es la
# cantidad o parte de la µ, y corregirlo podría inventar un número.
CONFUSIONES_OCR: dict[str, tuple[str, str]] = {
    # I mayúscula leída como l minúscula (vitamina E 10 Ul/kg, insulina 40 Ul/ml)
    "Ul": ("UI", "OCR: I → l"),
    "mUl": ("mUI", "OCR: I → l"),
    # m leída como rn (se ven casi iguales)
    "rng": ("mg", "OCR: m → rn"),
    "rnl": ("ml", "OCR: m → rn"),
    "rnL": ("mL", "OCR: m → rn"),
    "mrnol": ("mmol", "OCR: m → rn"),
    "rnmol": ("mmol", "OCR: m → rn"),
    "rnEq": ("mEq", "OCR: m → rn"),
    # letras mal leídas o perdidas
    "mmoi": ("mmol", "OCR: l → i"),
    "mmo": ("mmol", "OCR: letra perdida"),
    "mEg": ("mEq", "OCR: q → g"),
    "meg": ("mcg", "OCR: c → e"),
    # la µ leída de muchas formas
    **dict.fromkeys(
        ("llg", "IJg", "jig", "jUg", "jg", "xg", "wg", "Ug", "prg", "pcg", "yg"),
        ("µg", "OCR: µ mal leída"),
    ),
}


def corregir_confusiones_ocr(texto: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Corrige las confusiones del OCR en unidades compuestas (``5 rng/kg`` → ``5 mg/kg``).

    Returns:
        El texto corregido y una lista de ``(original, corregido, regla)``.
    """
    cambios: list[tuple[str, str, str]] = []

    def reemplazar(coincidencia: re.Match[str]) -> str:
        unidad = coincidencia.group("unidad")
        if unidad not in CONFUSIONES_OCR:
            return coincidencia.group(0)
        real, regla = CONFUSIONES_OCR[unidad]
        inicio = coincidencia.start("unidad") - coincidencia.start()
        fin = coincidencia.end("unidad") - coincidencia.start()
        original = coincidencia.group(0)
        corregido = original[:inicio] + real + original[fin:]
        cambios.append((original, corregido, regla))
        return corregido

    return PATRON_UNIDAD_COMPUESTA.sub(reemplazar, texto), cambios
