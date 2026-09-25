"""Punto de entrada de la F2: ``uv run vetrag-ingesta <paso>``.

Cada paso de la ingesta es un subcomando, para poder correrlos y revisarlos por separado:

    uv run vetrag-ingesta ocr --piloto
"""

import argparse
import logging
import os
from collections import Counter

from vetrag.config import obtener_configuracion
from vetrag.ingesta.ocr import ejecutar_ocr, escribir_manifiesto
from vetrag.ingesta.seleccion import filtrar_piloto, leer_lista_piloto, leer_seleccion

logger = logging.getLogger("vetrag.ingesta")


def _comando_ocr(argumentos: argparse.Namespace) -> None:
    configuracion = obtener_configuracion()
    documentos = leer_seleccion(configuracion.ruta_clasificacion / "inventario.csv")
    if argumentos.piloto:
        documentos = filtrar_piloto(documentos, leer_lista_piloto(configuracion.ruta_piloto))
    logger.info("OCR de %d documentos", len(documentos))

    resultados = ejecutar_ocr(
        documentos,
        configuracion.ruta_assets,
        configuracion.ruta_ocr,
        argumentos.trabajadores,
    )
    escribir_manifiesto(resultados, configuracion.ruta_ocr / "manifiesto.csv")

    conteo = Counter(r.estado for r in resultados)
    logger.info("Listo: %s", ", ".join(f"{estado}={n}" for estado, n in conteo.items()))


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingesta de documentos (F2).")
    parser.add_argument("-v", "--verbose", action="store_true", help="más detalle en el log")
    pasos = parser.add_subparsers(dest="paso", required=True)

    ocr = pasos.add_parser("ocr", help="paso 1: OCR de los PDFs que lo necesitan")
    ocr.add_argument("--piloto", action="store_true", help="solo los documentos de piloto.txt")
    ocr.add_argument(
        "--trabajadores",
        type=int,
        default=os.cpu_count() or 1,
        help="núcleos que usa ocrmypdf por documento",
    )
    ocr.set_defaults(funcion=_comando_ocr)
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
