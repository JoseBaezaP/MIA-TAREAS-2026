"""Pruebas del catálogo de unidades, con las unidades de las tablas de referencia
(Tabla 1: SI y derivadas; Tabla 2: prefijos; Tablas 3 y 4: anglosajonas)."""

import pytest

from vetrag.ingesta.unidades import (
    CONFUSIONES_OCR,
    buscar_unidades_desconocidas,
    corregir_confusiones_ocr,
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


@pytest.mark.parametrize("unidad", ["ma", "mo", "1a", "rng", "yg", "rnl", "Ul"])
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
        # Corpus completo: abreviaturas en inglés y frecuencias
        "200 mcg/kg IM",
        "100 units/kg",
        "5 Units/ml",
        "0,5 gm/kg",
        "3 veces/día",
        "350 mosmol/kg",
        "180 lat/min",
        "1000 PNU/mL",
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


@pytest.mark.parametrize(
    ("original", "esperado"),
    [
        # Ejemplos reales del corpus completo
        ("vitamina E a diario (10 Ul/kg)", "vitamina E a diario (10 UI/kg)"),
        ("jeringas de 40 Ul/ml para insulina", "jeringas de 40 UI/ml para insulina"),
        ("producción de orina < 7 rnl/kg", "producción de orina < 7 ml/kg"),
        ("Ketamina 5 rng/kg IV", "Ketamina 5 mg/kg IV"),
        ("Sodio 140 mrnol/l", "Sodio 140 mmol/l"),
        ("Potasio 4 rnEq/l", "Potasio 4 mEq/l"),
        ("100 IJg/ml (73 Ul/ml)", "100 µg/ml (73 UI/ml)"),
        ("20 a 35 jig/ml en niños", "20 a 35 µg/ml en niños"),
        ("respuesta (<7 yg/dl)", "respuesta (<7 µg/dl)"),
        ("|10 llg/kg|IV|", "|10 µg/kg|IV|"),
        ("200 meg/kg", "200 mcg/kg"),
    ],
)
def test_corrige_confusiones_del_ocr(original: str, esperado: str) -> None:
    corregido, cambios = corregir_confusiones_ocr(original)
    assert corregido == esperado
    assert cambios


@pytest.mark.parametrize(
    "texto",
    [
        "Mantenimiento 20 mi/kg/h",  # ¿ml? ¿mg? ambiguo
        "Heparina 100 u/kg",  # ¿U? ¿µ? ambiguo
        "Dioxinas 4 pg/kg",  # pico real
        "Proteína 1g/dl",  # "1 g/dl" real
        "Glucosa 5 mg/kg",  # correcto
        "Cpm~x (1Jg/ml)",  # ¿"1" es cantidad o parte de la µ? no se inventan números
    ],
)
def test_no_toca_ambiguas_ni_correctas(texto: str) -> None:
    corregido, cambios = corregir_confusiones_ocr(texto)
    assert corregido == texto
    assert cambios == []


def test_cada_correccion_es_una_unidad_conocida_y_lo_leido_no() -> None:
    for leido, (real, _regla) in CONFUSIONES_OCR.items():
        assert not es_unidad_conocida(leido), leido
        assert es_unidad_conocida(real), real
