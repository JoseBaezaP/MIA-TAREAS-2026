"""Pruebas de los detectores de señales (funciones puras)."""

import pytest

from vetrag.clasificacion import detectores
from vetrag.clasificacion.modelos import Idioma, Recomendacion, SenalRuido, TipoContenido

TEXTO_ES = (
    "El parvovirus canino es una de las enfermedades más frecuentes en los cachorros "
    "que no han sido vacunados. Se transmite por contacto con las heces de otros perros "
    "y puede causar vómito, diarrea con sangre y deshidratación. Para el diagnóstico se "
    "usa una prueba rápida y el tratamiento es de soporte con fluidos por vía intravenosa."
)
TEXTO_EN = (
    "Canine parvovirus is one of the most common diseases in puppies that have not been "
    "vaccinated. It is transmitted by contact with the feces of other dogs and can cause "
    "vomiting, bloody diarrhea and dehydration. For the diagnosis a rapid test is used and "
    "the treatment is supportive with intravenous fluids when they are needed by the animal."
)


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("certificado antibiótico ", True),
        ("Formato_de_Convocatoria__Diplomado_Superior_2024-2025", True),
        ("CURSO PELUQUERIA Y ESTETICA CANINA DISTANCIA 2-converted", True),
        ("calendario_Mayo", True),
        ("Farmacologia-Veterinaria-Tercera-Edicion-Sumano", False),
        ("enfermedades de los gatos ", False),
    ],
)
def test_tiene_nombre_ruido(nombre: str, esperado: bool) -> None:
    assert detectores.tiene_nombre_ruido(nombre) is esperado


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("6530481", True),
        ("12", True),
        ("oFHf2dnmLNRCFCmix4jVxPPhaR3YpmufpjcXrtsX", True),
        ("doc", True),
        ("Fauna-2p(1)", False),
        ("Interpretación de laboratorio(1)", False),
        ("24_mordeduras_picaduras", False),
    ],
)
def test_es_nombre_no_descriptivo(nombre: str, esperado: bool) -> None:
    assert detectores.es_nombre_no_descriptivo(nombre) is esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        (TEXTO_ES, Idioma.ESPANOL),
        (TEXTO_EN, Idioma.INGLES),
        (TEXTO_ES + " " + TEXTO_EN, Idioma.MIXTO),
        ("", Idioma.DESCONOCIDO),
    ],
)
def test_detectar_idioma(texto: str, esperado: Idioma) -> None:
    assert detectores.detectar_idioma(texto) is esperado


def test_calidad_texto_alta_para_texto_normal() -> None:
    calidad = detectores.calcular_calidad_texto(TEXTO_ES + " Dosis: 0.5 mg/kg cada 12 h.")
    assert calidad is not None
    assert calidad > 0.9


def test_calidad_texto_baja_para_ocr_danado() -> None:
    calidad = detectores.calcular_calidad_texto("l1I| ~~ ;:%& 3e# !!1 |l| xX9$ @@ q^p ¬¬ ##")
    assert calidad is not None
    assert calidad < detectores.CALIDAD_TEXTO_MINIMA


def test_calidad_texto_sin_texto() -> None:
    assert detectores.calcular_calidad_texto("   ") is None


@pytest.mark.parametrize(
    ("textos", "esperado"),
    [
        ([TEXTO_ES] * 10, TipoContenido.TEXTO),
        ([""] * 10, TipoContenido.ESCANEADO),
        ([TEXTO_ES] * 5 + [""] * 5, TipoContenido.MIXTO),
        ([""] + [TEXTO_ES] * 9, TipoContenido.TEXTO),  # la portada suele ser una imagen
        ([], TipoContenido.ESCANEADO),
    ],
)
def test_clasificar_tipo_contenido(textos: list[str], esperado: TipoContenido) -> None:
    tipo, _, _ = detectores.clasificar_tipo_contenido(textos)
    assert tipo is esperado


def test_extraer_muestra_legible_usa_la_pagina_con_mas_texto() -> None:
    muestra = detectores.extraer_muestra_legible(["Portada", "  El   parvovirus\ncanino  "])
    assert muestra == "El parvovirus canino"


@pytest.mark.parametrize(
    ("senales", "esperado"),
    [
        ([], Recomendacion.CONSERVAR),
        ([SenalRuido.NOMBRE_NO_DESCRIPTIVO], Recomendacion.REVISAR),
        ([SenalRuido.TEXTO_BAJA_CALIDAD], Recomendacion.REVISAR),
        ([SenalRuido.DUPLICADO], Recomendacion.DESCARTAR),
        ([SenalRuido.NOMBRE_NO_DESCRIPTIVO, SenalRuido.NOMBRE_RUIDO], Recomendacion.DESCARTAR),
    ],
)
def test_recomendar(senales: list[SenalRuido], esperado: Recomendacion) -> None:
    assert detectores.recomendar(senales) is esperado
