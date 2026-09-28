"""Pruebas del chunking."""

from itertools import count, pairwise
from pathlib import Path

from vetrag.clasificacion.modelos import TipoContenido
from vetrag.ingesta.chunking import (
    TOKENS_OBJETIVO,
    TOKENS_TRASLAPE,
    TipoBloque,
    construir_encabezado,
    contar_tokens,
    dividir_documento,
    ejecutar_chunking,
    leer_bloques,
    leer_cabecera,
    partir_parrafo,
    partir_tabla,
    titulo_legible,
)
from vetrag.ingesta.conversion import ruta_markdown
from vetrag.ingesta.seleccion import DocumentoSeleccionado

CABECERA = (
    '---\ndocumento: "Farmacologia+Veterinaria"\nespecialidad: "Farmacología"\n'
    'idioma: "es"\nfuente: "Bib/Farmacologia+Veterinaria.pdf"\npaginas: 3\n---\n\n'
)
ORACION = "El meloxicam es un antiinflamatorio no esteroideo que se usa en perros y gatos. "


_NUMERO = count(1)


def parrafo(tokens: int) -> str:
    """Un párrafo en español de ~``tokens`` tokens, con oraciones numeradas (todas distintas)."""
    oraciones: list[str] = []
    while contar_tokens(" ".join(oraciones)) < tokens:
        oraciones.append(f"Oración {next(_NUMERO)}: {ORACION.strip()}")
    return " ".join(oraciones)


def test_leer_cabecera() -> None:
    metadatos = leer_cabecera(CABECERA)
    assert metadatos["especialidad"] == "Farmacología"
    assert metadatos["paginas"] == 3


def test_leer_bloques_con_paginas_y_rutas() -> None:
    cuerpo = (
        "<!-- pagina: 1 -->\n# Antiinflamatorios\n\n## Meloxicam\n\nTexto uno.\n\n"
        "<!-- pagina: 2 -->\nTexto dos.\n\n## Carprofeno\n\n|a|b|\n|---|---|\n|1|2|\n"
    )
    bloques = leer_bloques(cuerpo)
    contenido = [b for b in bloques if b.tipo is not TipoBloque.TITULO]
    assert [(b.texto, b.pagina, b.ruta_titulos) for b in contenido] == [
        ("Texto uno.", 1, ("Antiinflamatorios", "Meloxicam")),
        ("Texto dos.", 2, ("Antiinflamatorios", "Meloxicam")),
        ("|a|b|\n|---|---|\n|1|2|", 2, ("Antiinflamatorios", "Carprofeno")),
    ]
    assert contenido[-1].tipo is TipoBloque.TABLA


def test_titulo_demasiado_largo_es_un_parrafo() -> None:
    (bloque,) = leer_bloques("## " + "palabra " * 40)
    assert bloque.tipo is TipoBloque.PARRAFO


def test_no_corta_entre_etiqueta_y_valor() -> None:
    pedazos = partir_parrafo(parrafo(1000) + " Dosis: 0,1 mg/kg cada 24 h.")
    assert any("Dosis: 0,1 mg/kg cada 24 h." in p for p in pedazos)


def test_partir_parrafo_no_corta_oraciones() -> None:
    pedazos = partir_parrafo(parrafo(2000))
    assert len(pedazos) > 1
    assert all(contar_tokens(p) <= TOKENS_OBJETIVO for p in pedazos)
    assert all(p.endswith(".") for p in pedazos)


def test_partir_tabla_repite_el_encabezado() -> None:
    filas = "\n".join(f"|Fármaco {i}|0,1-0,5 mg/kg IV|" for i in range(400))
    tabla = "|Fármaco|Dosis|\n|---|---|\n" + filas
    pedazos = partir_tabla(tabla)
    assert len(pedazos) > 1
    assert all(p.startswith("|Fármaco|Dosis|\n|---|---|") for p in pedazos)
    total_filas = sum(len(p.splitlines()) - 2 for p in pedazos)
    assert total_filas == 400  # no se pierde ni se repite ninguna fila


def test_seccion_larga_se_divide_con_traslape() -> None:
    cuerpo = "<!-- pagina: 1 -->\n## Meloxicam\n\n" + "\n\n".join(parrafo(300) for _ in range(8))
    chunks = dividir_documento(CABECERA + cuerpo)
    assert len(chunks) >= 3
    assert all(c.tokens <= TOKENS_OBJETIVO + TOKENS_TRASLAPE for c in chunks)
    # El chunk siguiente empieza con una oración que ya estaba al final del anterior.
    for anterior, siguiente in pairwise(chunks):
        primera_oracion = siguiente.texto.split(". ")[0]
        assert primera_oracion in anterior.texto
        assert anterior.texto.index(primera_oracion) > len(anterior.texto) // 2


def test_no_mezcla_secciones_ni_hace_traslape_entre_ellas() -> None:
    cuerpo = f"## Meloxicam\n\n{parrafo(300)}\n\n## Carprofeno\n\nEl carprofeno {parrafo(300)}"
    meloxicam, carprofeno = dividir_documento(CABECERA + cuerpo)
    assert meloxicam.ruta_titulos == ["Meloxicam"]
    assert carprofeno.ruta_titulos == ["Carprofeno"]
    assert carprofeno.texto.startswith("El carprofeno")  # sin traslape de la otra sección


def test_seccion_corta_se_une_con_la_siguiente() -> None:
    cuerpo = f"## Introducción\n\nBreve.\n\n## Meloxicam\n\n{parrafo(300)}"
    (chunk,) = dividir_documento(CABECERA + cuerpo)
    assert chunk.texto.startswith("Breve.")  # la sección corta no se perdió
    assert chunk.ruta_titulos == ["Meloxicam"]


def test_paginas_idioma_y_encabezado() -> None:
    cuerpo = (
        f"<!-- pagina: 1 -->\n## Meloxicam\n\n{parrafo(200)}\n\n<!-- pagina: 2 -->\n{parrafo(200)}"
    )
    (chunk,) = dividir_documento(CABECERA + cuerpo)
    assert (chunk.pagina_inicio, chunk.pagina_fin) == (1, 2)
    assert chunk.idioma == "es"
    assert chunk.documento == "Farmacologia Veterinaria"
    assert chunk.texto_para_embedding.startswith(
        "Documento: Farmacologia Veterinaria | Especialidad: Farmacología\n"
        "Sección: Meloxicam\n---\n"
    )


def test_unidades_dudosas_quedan_en_el_chunk() -> None:
    cuerpo = f"## Ketamina\n\n{parrafo(150)} Bolo carga: 0,5-1 ma/kg IV."
    (chunk,) = dividir_documento(CABECERA + cuerpo)
    assert len(chunk.unidades_dudosas) == 1
    assert "ma/kg" in chunk.unidades_dudosas[0]


def test_ids_distintos_y_estables() -> None:
    cuerpo = "## A\n\n" + "\n\n".join(parrafo(300) for _ in range(6))
    primera = dividir_documento(CABECERA + cuerpo)
    segunda = dividir_documento(CABECERA + cuerpo)
    assert len({c.id for c in primera}) == len(primera)
    assert [c.id for c in primera] == [c.id for c in segunda]


def test_utilidades() -> None:
    assert titulo_legible("Anatomia+de+los_Animales") == "Anatomia de los Animales"
    assert (
        construir_encabezado("Libro", "Cirugía", []) == "Documento: Libro | Especialidad: Cirugía"
    )
    assert contar_tokens("") == 0


def test_ejecutar_chunking_descarta_duplicados(tmp_path: Path) -> None:
    limpio = tmp_path / "limpio"
    texto = CABECERA + f"## Meloxicam\n\n{parrafo(300)}"
    documentos = []
    for nombre in ("libro.pdf", "copia.pdf"):
        doc = DocumentoSeleccionado(
            Path("Bib") / nombre, "Farmacología", TipoContenido.TEXTO, "es", 0.9, 3
        )
        destino = ruta_markdown(limpio, doc.ruta_relativa)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")  # el mismo texto en los dos
        documentos.append(doc)
    resumen = ejecutar_chunking(documentos, limpio, tmp_path / "chunks.jsonl")
    assert resumen.chunks == 1
    assert resumen.duplicados_descartados == 1
    assert len((tmp_path / "chunks.jsonl").read_text().splitlines()) == 1
