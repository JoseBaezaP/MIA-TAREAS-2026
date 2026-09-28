"""Punto de entrada de la F2: ``uv run vetrag-ingesta <paso>``.

Cada paso de la ingesta es un subcomando, para poder correrlos y revisarlos por separado:

    uv run vetrag-ingesta ocr --piloto
    uv run vetrag-ingesta convertir --piloto
    uv run vetrag-ingesta limpiar --piloto
    uv run vetrag-ingesta chunks --piloto
    uv run vetrag-ingesta vectorizar --piloto
"""

import argparse
import json
import logging
import os
from collections import Counter
from dataclasses import asdict

from vetrag.base_datos.conexion import conectar, crear_esquema
from vetrag.base_datos.repositorio_chunks import RepositorioChunks
from vetrag.config import Configuracion, obtener_configuracion
from vetrag.ingesta import chunking, conversion, limpieza, ocr, vectorizacion
from vetrag.ingesta.seleccion import (
    DocumentoSeleccionado,
    filtrar_piloto,
    leer_lista_piloto,
    leer_seleccion,
)

logger = logging.getLogger("vetrag.ingesta")


def _documentos(configuracion: Configuracion, piloto: bool) -> list[DocumentoSeleccionado]:
    documentos = leer_seleccion(configuracion.ruta_clasificacion / "inventario.csv")
    if piloto:
        documentos = filtrar_piloto(documentos, leer_lista_piloto(configuracion.ruta_piloto))
    return documentos


def _resumir(estados: list[str]) -> None:
    conteo = Counter(estados)
    logger.info("Listo: %s", ", ".join(f"{estado}={n}" for estado, n in conteo.items()))


def _comando_ocr(argumentos: argparse.Namespace) -> None:
    configuracion = obtener_configuracion()
    documentos = _documentos(configuracion, argumentos.piloto)
    logger.info("OCR de %d documentos", len(documentos))
    resultados = ocr.ejecutar_ocr(
        documentos,
        configuracion.ruta_assets,
        configuracion.ruta_ocr,
        argumentos.trabajadores,
    )
    ocr.escribir_manifiesto(resultados, configuracion.ruta_ocr / "manifiesto.csv")
    _resumir([r.estado for r in resultados])


def _comando_convertir(argumentos: argparse.Namespace) -> None:
    configuracion = obtener_configuracion()
    documentos = _documentos(configuracion, argumentos.piloto)
    fuentes = conversion.leer_manifiesto_ocr(configuracion.ruta_ocr / "manifiesto.csv")
    logger.info("Conversión a Markdown de %d documentos", len(documentos))
    resultados = conversion.ejecutar_conversion(documentos, fuentes, configuracion.ruta_markdown)
    conversion.escribir_manifiesto(resultados, configuracion.ruta_markdown / "manifiesto.csv")
    _resumir([r.estado for r in resultados])


def _comando_limpiar(argumentos: argparse.Namespace) -> None:
    configuracion = obtener_configuracion()
    documentos = _documentos(configuracion, argumentos.piloto)
    logger.info("Limpieza de %d documentos", len(documentos))
    con_ocr = ocr.leer_documentos_con_ocr(configuracion.ruta_ocr / "manifiesto.csv")
    resultados, reporte = limpieza.ejecutar_limpieza(
        documentos, configuracion.ruta_markdown, configuracion.ruta_limpio, con_ocr
    )
    limpieza.escribir_manifiesto(resultados, configuracion.ruta_limpio / "manifiesto.csv")
    limpieza.escribir_reporte(reporte, configuracion.ruta_limpio / "reporte_limpieza.csv")
    _resumir([str(c.tipo) for _, c in reporte])


def _comando_chunks(argumentos: argparse.Namespace) -> None:
    configuracion = obtener_configuracion()
    documentos = _documentos(configuracion, argumentos.piloto)
    logger.info("Chunking de %d documentos", len(documentos))
    resumen = chunking.ejecutar_chunking(
        documentos, configuracion.ruta_limpio, configuracion.ruta_chunks / "chunks.jsonl"
    )
    ruta_resumen = configuracion.ruta_chunks / "resumen.json"
    ruta_resumen.write_text(json.dumps(asdict(resumen), indent=2), encoding="utf-8")
    logger.info("Listo: %s", asdict(resumen))


def _comando_vectorizar(argumentos: argparse.Namespace) -> None:
    configuracion = obtener_configuracion()
    if configuracion.voyage_api_key is None or configuracion.database_url is None:
        raise SystemExit("Faltan VETRAG_VOYAGE_API_KEY o VETRAG_DATABASE_URL en backend/.env")
    fuentes = None
    if argumentos.piloto:
        fuentes = {str(d.ruta_relativa) for d in _documentos(configuracion, piloto=True)}
    chunks = list(vectorizacion.leer_chunks(configuracion.ruta_chunks / "chunks.jsonl", fuentes))
    vectorizador = vectorizacion.VectorizadorVoyage(
        configuracion.voyage_api_key.get_secret_value(), configuracion.modelo_embedding
    )
    with conectar(configuracion.database_url.get_secret_value()) as conexion:
        crear_esquema(conexion)
        repositorio = RepositorioChunks(conexion)
        resumen = vectorizacion.ejecutar_vectorizacion(
            chunks, vectorizador, repositorio, configuracion.limite_tokens_voyage
        )
        if not resumen.detenido_por_limite:
            logger.info("Creando el índice vectorial HNSW…")
            repositorio.crear_indice_vectorial()
        logger.info("Listo: %s | chunks en la base: %d", asdict(resumen), repositorio.contar())


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingesta de documentos (F2).")
    parser.add_argument("-v", "--verbose", action="store_true", help="más detalle en el log")
    pasos = parser.add_subparsers(dest="paso", required=True)

    parser_ocr = pasos.add_parser("ocr", help="paso 1: OCR de los PDFs que lo necesitan")
    parser_ocr.add_argument(
        "--piloto", action="store_true", help="solo los documentos de piloto.txt"
    )
    parser_ocr.add_argument(
        "--trabajadores",
        type=int,
        default=os.cpu_count() or 1,
        help="núcleos que usa ocrmypdf por documento",
    )
    parser_ocr.set_defaults(funcion=_comando_ocr)

    parser_convertir = pasos.add_parser("convertir", help="paso 2: documentos → Markdown")
    parser_convertir.add_argument(
        "--piloto", action="store_true", help="solo los documentos de piloto.txt"
    )
    parser_convertir.set_defaults(funcion=_comando_convertir)

    parser_limpiar = pasos.add_parser("limpiar", help="paso 3: limpieza del Markdown")
    parser_limpiar.add_argument(
        "--piloto", action="store_true", help="solo los documentos de piloto.txt"
    )
    parser_limpiar.set_defaults(funcion=_comando_limpiar)

    parser_chunks = pasos.add_parser("chunks", help="paso 4: división en chunks")
    parser_chunks.add_argument(
        "--piloto", action="store_true", help="solo los documentos de piloto.txt"
    )
    parser_chunks.set_defaults(funcion=_comando_chunks)

    parser_vectorizar = pasos.add_parser(
        "vectorizar", help="paso 5: embeddings con Voyage → pgvector"
    )
    parser_vectorizar.add_argument(
        "--piloto", action="store_true", help="solo los documentos de piloto.txt"
    )
    parser_vectorizar.set_defaults(funcion=_comando_vectorizar)
    return parser.parse_args()


def main() -> None:
    """Ejecuta el paso de la ingesta indicado en la línea de comandos."""
    argumentos = _argumentos()
    logging.basicConfig(
        level=logging.DEBUG if argumentos.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    argumentos.funcion(argumentos)


if __name__ == "__main__":
    main()
