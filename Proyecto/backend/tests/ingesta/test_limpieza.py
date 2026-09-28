"""Pruebas de la limpieza, con ejemplos reales del piloto (incluidas las "trampas")."""

import pytest

from vetrag.ingesta.limpieza import (
    MARCA_DATO_PERSONAL,
    Pagina,
    TipoCambio,
    clave_linea,
    corregir_unidades,
    detectar_lineas_repetidas,
    dividir_paginas,
    limpiar_markdown,
    quitar_datos_personales,
    quitar_lineas_repetidas,
    quitar_numeros_pagina,
    separar_cabecera,
    unir,
)

# --- Estructura -----------------------------------------------------------------------


def test_separar_cabecera() -> None:
    cabecera, cuerpo = separar_cabecera('---\ndocumento: "x"\n---\n\n<!-- pagina: 1 -->\nHola')
    assert cabecera == '---\ndocumento: "x"\n---\n'
    assert cuerpo.strip().endswith("Hola")


def test_dividir_y_unir_conserva_las_marcas() -> None:
    cuerpo = "<!-- pagina: 1 -->\nUno\n\n<!-- pagina: 2 -->\nDos\n"
    paginas = dividir_paginas(cuerpo)
    assert [(p.numero, p.texto.strip()) for p in paginas] == [(1, "Uno"), (2, "Dos")]
    assert unir(paginas) == cuerpo


def test_documento_sin_paginas() -> None:
    (pagina,) = dividir_paginas("## Sangre\n\n- Hemoglobina\n")
    assert pagina.numero is None
    assert unir([pagina]) == "## Sangre\n\n- Hemoglobina\n"


# --- 1. Líneas repetidas ----------------------------------------------------------------


def test_clave_linea_conserva_numeros_internos() -> None:
    assert clave_linea("La catalasa 3 descompone") != clave_linea("La catalasa 4 descompone")
    assert clave_linea("12 Capítulo 5") == clave_linea("13 Capítulo 5")


def test_clave_linea_ignora_numeros_de_los_extremos() -> None:
    a = "*Alfredo Wong González y Jesús Jaime Hernández Escareño* Página 12"
    b = "*Alfredo Wong González y Jesús Jaime Hernández Escareño* Página 13"
    assert clave_linea(a) == clave_linea(b)


def _paginas(textos: list[str]) -> list[Pagina]:
    return [Pagina(i, t) for i, t in enumerate(textos, start=1)]


def test_quita_encabezado_y_pie_repetidos() -> None:
    paginas = _paginas(
        [
            f"*Manual de Prácticas Departamento de Microbiología*\nContenido {i} de la práctica\n"
            f"*Alfredo Wong González* Página {i}"
            for i in range(1, 7)
        ]
    )
    cambios = quitar_lineas_repetidas(paginas)
    assert {c.original for c in cambios} == {
        "*Manual de Prácticas Departamento de Microbiología*",
        "*Alfredo Wong González* Página 1",
    }
    assert all(p.texto.strip().startswith("Contenido") for p in paginas)


def test_trampa_no_toca_lineas_de_tabla() -> None:
    paginas = _paginas(["|a|b|\n|---|---|\n|1|2|"] * 6)
    assert detectar_lineas_repetidas(paginas) == {}


def test_trampa_documentos_cortos_no_se_revisan() -> None:
    paginas = _paginas(["Agosto 2019\nTexto"] * 4)
    assert detectar_lineas_repetidas(paginas) == {}


def test_linea_que_aparece_en_pocas_paginas_se_queda() -> None:
    paginas = _paginas(["Parvovirus"] * 2 + ["Otro tema"] * 4)
    assert "Parvovirus" not in detectar_lineas_repetidas(paginas)


# --- 2. Datos personales -------------------------------------------------------------------


def test_etiqueta_nombre_y_matricula() -> None:
    linea = (
        "Escobedo, Nuevo León, enero de 2020 "
        "**Nombre: Pouda Arguello Sheril Marisol, Matricula: 1811158, Grupo: 42**"
    )
    texto, cambios = quitar_datos_personales(linea)
    assert texto == (
        f"Escobedo, Nuevo León, enero de 2020 **{MARCA_DATO_PERSONAL}, {MARCA_DATO_PERSONAL}"
        ", Grupo: 42**"
    )
    assert "1811158" not in texto
    assert cambios[0].tipo is TipoCambio.DATO_PERSONAL


def test_caso_clinico_conserva_los_datos_clinicos() -> None:
    linea = "Nombre: Mimo Especie: Felina Raza: Persa Sexo: Macho Edad: 7 años Peso: 3,5 kg"
    limpio, cambios = quitar_datos_personales(linea)
    assert limpio == (
        f"{MARCA_DATO_PERSONAL} Especie: Felina Raza: Persa Sexo: Macho Edad: 7 años Peso: 3,5 kg"
    )
    assert cambios[0].original == "Nombre: Mimo"


def test_lista_de_equipo() -> None:
    texto = (
        "## Sangre\n\nFisiología Veterinaria\n\nEquipo:\n\nDaniela Itzel Pérez Mayo 1942060\n\n"
        "Mariana Rosales Salazar 1850088\n\nCinthia Yareli Torres Reina\n\n"
        "**UNIVERSIDAD AUTÓNOMA DE NUEVO LEÓN**"
    )
    limpio, cambios = quitar_datos_personales(texto)
    assert "Daniela" not in limpio
    assert "Cinthia" not in limpio
    assert "UNIVERSIDAD AUTÓNOMA DE NUEVO LEÓN" in limpio
    assert len(cambios) == 3


@pytest.mark.parametrize(
    "linea", ["Nombre: Pouda Arguello", "**Nombre: Pouda Arguello**", "|Nombre: Ana Pérez|"]
)
def test_etiqueta_al_inicio_de_linea_o_celda(linea: str) -> None:
    limpio, _ = quitar_datos_personales(linea)
    assert "Pouda" not in limpio
    assert "Ana" not in limpio


def test_nombre_con_matricula_sin_etiqueta() -> None:
    limpio, _ = quitar_datos_personales("Monserrat Guadalupe Villegas Cruz 1922334")
    assert limpio == MARCA_DATO_PERSONAL


@pytest.mark.parametrize(
    "linea",
    [
        "Teléfono: 847-925-8070",
        "Tel. (81) 1234-5678",
        "Llamar al +52 81 1234 5678 para citas",
        "Consultas: 81-1234-5678",
        "contacto: ana.perez@uanl.edu.mx",
    ],
)
def test_telefonos_y_correos(linea: str) -> None:
    limpio, cambios = quitar_datos_personales(linea)
    assert MARCA_DATO_PERSONAL in limpio
    assert cambios


@pytest.mark.parametrize(
    "linea",
    [
        # "propietario" como palabra normal (sin dos puntos)
        "Realizar el tratamiento según la disponibilidad y conformidad del propietario.",
        # "colonia" bacteriana (por esto no hay regla de direcciones)
        "Con el asa, recoger el centro de la colonia bacteriana de la caja de Petri.",
        # "Paciente:" describe al animal: es un dato clínico
        "Paciente: canino, macho, 5 años, con poliuria y polidipsia.",
        # autor de un libro (dato público)
        "GUSTAVO MACHICOTE GOTH Licenciado en Veterinaria por la Universidad de Buenos Aires.",
        # epónimos médicos
        "Síndrome de Cushing y enfermedad de Addison en perros.",
        # "Otros nombres:" en razas de perro (corpus completo)
        "Otros nombres: Bobtail Japonés",
        "Otros nombres: Lakeland, Lakie, Patterdale terrier, Fell terrier",
        # "nombre:" a mitad de oración
        "También se conoce con el nombre: fibrosis hepatoportal en 3 perros",
        # volumen y años en una referencia bibliográfica
        "J Vet Intern Med (250) 1996-1998.",
        # dosis y rangos numéricos no son teléfonos
        "Dosis: 0,1-0,5 mg/kg IV cada 12 h; 10-20 µg/kg IM.",
        "Hematocrito 37-55 %, plaquetas 200 000-500 000 /µL",
        # filas de tablas con números separados por espacios (corpus completo)
        "|600 3200 6400|",
        "62 6063 6164",
    ],
)
def test_trampas_datos_personales_no_se_borran(linea: str) -> None:
    limpio, cambios = quitar_datos_personales(linea)
    assert limpio == linea
    assert cambios == []


# --- 3. Unidades ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("original", "esperado"),
    [
        ("Medetomidina 5-10 pg/kg IV", "Medetomidina 5-10 µg/kg IV"),
        ("Bolo carga: 5 yg/kg y", "Bolo carga: 5 µg/kg y"),
        ("|10-20|pg/kg|IM|", "|10-20|µg/kg|IM|"),
        ("CRI: 2-10 1g/kg/h", "CRI: 2-10 µg/kg/h"),
    ],
)
def test_corrige_micro_mal_leido_en_documentos_con_ocr(original: str, esperado: str) -> None:
    corregido, cambios = corregir_unidades(original, con_ocr=True)
    assert corregido == esperado
    assert cambios[0].tipo is TipoCambio.UNIDAD_CORREGIDA


def test_mu_griega_se_unifica_con_otra_regla() -> None:
    corregido, cambios = corregir_unidades("Dosis 2,5 μg/kg IV")
    assert corregido == "Dosis 2,5 µg/kg IV"
    assert cambios[0].regla.startswith("μ griega")


@pytest.mark.parametrize("texto", ["CRI: 1-2 ug/kg", "CRI: 0,5-1 ug/kg/h", "ACTH 10 ug/dl"])
def test_ug_se_corrige_siempre(texto: str) -> None:
    corregido, _ = corregir_unidades(texto, con_ocr=False)
    assert "µg/" in corregido
    assert "ug/" not in corregido


def test_trampa_pg_real_en_documento_digital() -> None:
    # En un PDF digital el texto es exacto: "pg/kg" es un dato real (p. ej. residuos).
    texto = "Dioxinas en carne: máximo 4 pg/kg IV"
    corregido, cambios = corregir_unidades(texto, con_ocr=False)
    assert corregido == texto
    assert cambios == []


def test_trampa_pg_sin_contexto_de_dosis_no_se_corrige() -> None:
    texto = "Límite de residuos en leche: 3 pg/kg de grasa"
    corregido, _ = corregir_unidades(texto, con_ocr=True)
    assert corregido == texto


@pytest.mark.parametrize(
    "texto",
    [
        "Glucosa 0,5 g/kg IV",
        "Ketamina 2-6 mg/kg IV",
        "Fluidos 20 ml/kg/h",
        "0,1g/kg",
        "Molalidad 0,3 mol/kg",
        "Sodio 145 mmol/l",
        "Potasio 4 mval/l",
        "Residuo 1 ng/kg",
        "Amoxicilina 10 mg/lb VO",
    ],
)
def test_trampa_unidades_reales_no_se_tocan(texto: str) -> None:
    corregido, cambios = corregir_unidades(texto, con_ocr=True)
    assert corregido == texto
    assert cambios == []


@pytest.mark.parametrize(
    "texto", ["CRI: 0,5-1 1a/kg/h", "doxiciclina 5 ma/kg", "Morfina 0,1-0,5 mo/kg IM"]
)
def test_unidad_fuera_del_catalogo_solo_se_reporta(texto: str) -> None:
    corregido, cambios = corregir_unidades(texto, con_ocr=True)
    assert corregido == texto
    assert [c.tipo for c in cambios] == [TipoCambio.UNIDAD_SOSPECHOSA]


# --- 4. Números de página -------------------------------------------------------------------


@pytest.mark.parametrize(
    "linea", ["12", "- 12 -", "Página 12", "pág. 3", "12 de 40", "Pagina 7/42"]
)
def test_quita_numeros_de_pagina(linea: str) -> None:
    texto, cambios = quitar_numeros_pagina(f"Texto\n{linea}\nMás texto")
    assert texto == "Texto\nMás texto"
    assert len(cambios) == 1


def test_trampa_numeros_con_contexto_se_quedan() -> None:
    texto = "Dosis 12 mg\n1. Introducción\n2019"
    limpio, _ = quitar_numeros_pagina(texto)
    assert "Dosis 12 mg" in limpio
    assert "1. Introducción" in limpio


# --- Documento completo ---------------------------------------------------------------------


def test_limpiar_markdown_completo() -> None:
    paginas = "\n\n".join(
        f"<!-- pagina: {i} -->\n*Manual de Prácticas*\n\n"
        f"La catalasa {i} descompone el peróxido.\n\n{i}"
        for i in range(1, 7)
    )
    markdown = '---\ndocumento: "Manual"\n---\n\n' + paginas
    limpio = limpiar_markdown(markdown)
    assert limpio.texto.startswith('---\ndocumento: "Manual"\n---\n')
    assert limpio.texto.count("<!-- pagina:") == 6
    assert "*Manual de Prácticas*" not in limpio.texto
    assert "La catalasa 3 descompone" in limpio.texto
    # El número suelto de cada página se repite en todas, así que sale como línea repetida.
    assert all(not linea.strip().isdigit() for linea in limpio.texto.splitlines())
    assert {c.tipo for c in limpio.cambios} == {TipoCambio.LINEA_REPETIDA}
