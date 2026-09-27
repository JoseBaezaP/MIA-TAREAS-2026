"""Pruebas del catálogo de unidades, con las unidades de las tablas de referencia
(Tabla 1: SI y derivadas; Tabla 2: prefijos; Tablas 3 y 4: anglosajonas)."""

import pytest

from vetrag.ingesta.unidades import (
    buscar_unidades_desconocidas,
    es_unidad_conocida,
    tiene_contexto_de_dosis,
)


@pytest.mark.parametrize(
    "unidad",
    [
        # Tabla 2: prefijos sobre el gramo, de mega a pico
        "Mg", "kg", "hg", "dag", "dg", "cg", "mg", "µg", "μg", "ug", "ng", "pg",
        # Tabla 1: mol, molar, val, litro, katal, unidad
        "mol", "mmol", "µmol", "M", "mM", "val", "mval", "l", "ml", "dl", "kat", "U",
        # Tabla 1 (continuación): presión, energía, radiactividad
        "Pa", "kPa", "mbar", "atm", "mmHg", "Torr", "J", "kcal", "Bq", "Ci", "Gy",
        # Tabla 2: expresiones especiales
        "ppm", "ppb", "ppt", "%", "‰",
        # Tablas 3 y 4: anglosajonas
        "gr", "dr", "oz", "lb", "pt", "qt", "gal", "minim",
        # Clínicas
        "mEq", "mOsm", "UI", "mUI", "IU", "gotas",
        # Tabla 1: miliamperio (radiología) — distinto de "ma"
        "mA",
        # Todo en mayúsculas, común en tablas
        "MG", "ML", "MEQ",
    ],
)  # fmt: skip
def test_unidades_reales_estan_en_el_catalogo(unidad: str) -> None:
    assert es_unidad_conocida(unidad)


@pytest.mark.parametrize("unidad", ["ma", "mo", "1a", "rng", "yg", "rnl"])
def test_errores_de_ocr_no_estan_en_el_catalogo(unidad: str) -> None:
    assert not es_unidad_conocida(unidad)


@pytest.mark.parametrize(
    ("linea", "esperado"),
    [
        ("Medetomidina 5-10 µg/kg IV", True),
        ("Bolo carga: 5 µg/kg", True),
        ("CRI: 1-2 µg/kg/h", True),
        ("0,1 mg/kg cada 12 h", True),
        ("Límite de residuos en leche: 3 pg/kg de grasa", False),
        ("La imagen muestra el tejido", False),  # "im" dentro de una palabra no cuenta
    ],
)
def test_contexto_de_dosis(linea: str, esperado: bool) -> None:
    assert tiene_contexto_de_dosis(linea) is esperado


@pytest.mark.parametrize(
    "texto",
    [
        "1 mval/l = 1 mmol/l para iones monovalentes",  # Tabla 1
        "1 ppb = 1 µg/kg; 1 ppt = 1 ng/kg",  # Tabla 2
        "Sodio 145 mEq/L, osmolaridad 300 mOsm/l",
        "Infusión de dopamina 5 µg/kg/min",
        "Dosis 10 mg/lb",
    ],
)
def test_sin_falsas_alarmas(texto: str) -> None:
    assert buscar_unidades_desconocidas(texto) == []


def test_detecta_unidades_desconocidas() -> None:
    sospechosas = buscar_unidades_desconocidas("CRI: 0,5-1 1a/kg/h; doxiciclina 5 ma/kg")
    assert len(sospechosas) == 2


def test_se_respetan_mayusculas() -> None:
    assert es_unidad_conocida("mA")  # miliamperio
    assert not es_unidad_conocida("ma")  # "mg" mal leído
    assert es_unidad_conocida("M")  # molar
