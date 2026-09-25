"""Punto de entrada de la F1: ``uv run vetrag-clasificar``."""

import argparse
import logging
import time
from pathlib import Path

from vetrag.clasificacion.inventario import construir_inventario
from vetrag.clasificacion.reporte import escribir_csv, escribir_resumen
from vetrag.config import obtener_configuracion

logger = logging.getLogger("vetrag.clasificacion")


def _argumentos() -> argparse.Namespace:
    configuracion = obtener_configuracion()
    parser = argparse.ArgumentParser(
        description="Clasifica los archivos de assets/ y genera el inventario del corpus."
    )
    parser.add_argument("--assets", type=Path, default=configuracion.ruta_assets)
    parser.add_argument("--salida", type=Path, default=configuracion.ruta_clasificacion)
    parser.add_argument("--trabajadores", type=int, default=None, help="procesos en paralelo")
    parser.add_argument("-v", "--verbose", action="store_true", help="más detalle en el log")
    return parser.parse_args()


def main() -> None:
    """Genera ``inventario.csv`` y ``resumen.md``."""
    argumentos = _argumentos()
    logging.basicConfig(
        level=logging.DEBUG if argumentos.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    def al_avanzar(procesados: int, total: int) -> None:
        if procesados % 25 == 0 or procesados == total:
            logger.info("Progreso: %d/%d", procesados, total)

    inicio = time.perf_counter()
    registros = construir_inventario(argumentos.assets, argumentos.trabajadores, al_avanzar)
    escribir_csv(registros, argumentos.salida / "inventario.csv")
    escribir_resumen(registros, argumentos.salida / "resumen.md")
    logger.info(
        "Listo en %.0f s: %d archivos → %s",
        time.perf_counter() - inicio,
        len(registros),
        argumentos.salida,
    )


if __name__ == "__main__":
    main()
