"""Punto de entrada de la F2: ``uv run vetrag-ingesta <paso>``.

Cada paso de la ingesta es un subcomando, para poder correrlos y revisarlos por separado:

    uv run vetrag-ingesta ocr --piloto
    uv run vetrag-ingesta convertir --piloto
    uv run vetrag-ingesta limpiar --piloto
"""

import argparse
import logging
import os
from collections import Counter

from vetrag.config import Configuracion, obtener_configuracion
from vetrag.ingesta import conversion, limpieza, ocr
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
