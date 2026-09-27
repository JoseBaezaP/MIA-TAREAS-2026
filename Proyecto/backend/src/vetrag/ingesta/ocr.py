"""Paso 1 de la F2: OCR con ``ocrmypdf`` para que todos los PDFs tengan texto extraíble.

Nunca se modifica el original: el PDF con OCR se escribe en ``data/02_ocr/`` con la misma
ruta de carpetas. Al final se escribe un *manifiesto* que indica, para cada documento, qué
archivo debe leer el paso siguiente (el PDF con OCR o el original).
"""

import csv
import logging
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from vetrag.clasificacion.detectores import CALIDAD_TEXTO_MINIMA
from vetrag.clasificacion.modelos import TipoContenido
from vetrag.ingesta.seleccion import DocumentoSeleccionado, normalizar_ruta

logger = logging.getLogger(__name__)

IDIOMAS_OCR = "spa+eng"
LINEAS_ERROR_A_GUARDAR = 5


class ModoOcr(StrEnum):
    """Qué hacer con un documento en el paso de OCR."""

    NO_APLICA = "no_aplica"  # no es PDF (PowerPoint, Word…)
    NO_NECESARIO = "no_necesario"  # ya tiene texto de buena calidad
    COMPLETAR = "completar"  # --skip-text: OCR solo en páginas sin texto
    REHACER = "rehacer"  # --redo-ocr: reemplaza un OCR viejo de mala calidad


class EstadoOcr(StrEnum):
    """Resultado del paso para un documento."""

    PROCESADO = "procesado"
    YA_EXISTIA = "ya_existia"  # se procesó en una corrida anterior
    OMITIDO = "omitido"  # no necesitaba OCR
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ResultadoOcr:
    """Una fila del manifiesto."""

    ruta_relativa: Path
    modo: ModoOcr
    estado: EstadoOcr
    ruta_fuente: Path  # archivo que debe leer el paso siguiente
    segundos: float = 0.0
    mensaje: str = ""


def elegir_modo_ocr(documento: DocumentoSeleccionado) -> ModoOcr:
    """Decide el modo de OCR a partir de lo que se sabe del documento en la F1."""
    if documento.tipo_contenido is TipoContenido.DOCUMENTO:
        return ModoOcr.NO_APLICA
    calidad = documento.calidad_texto
    if calidad is not None and calidad < CALIDAD_TEXTO_MINIMA:
        return ModoOcr.REHACER
    if documento.tipo_contenido in (TipoContenido.ESCANEADO, TipoContenido.MIXTO):
        return ModoOcr.COMPLETAR
    return ModoOcr.NO_NECESARIO


def construir_comando(modo: ModoOcr, entrada: Path, salida: Path, trabajadores: int) -> list[str]:
    """Arma el comando de ``ocrmypdf`` para un modo que sí requiere OCR."""
    comando = [
        "ocrmypdf",
        "--language", IDIOMAS_OCR,
        "--output-type", "pdf",  # PDF normal: más rápido que PDF/A y sin alterar el original
        "--optimize", "0",  # sin recomprimir imágenes: más rápido
        "--jobs", str(trabajadores),
    ]  # fmt: skip
    if modo is ModoOcr.COMPLETAR:
        comando += ["--skip-text", "--rotate-pages", "--deskew"]
    elif modo is ModoOcr.REHACER:
        comando += ["--redo-ocr"]
    else:
        raise ValueError(f"El modo {modo} no ejecuta OCR")
    return [*comando, str(entrada), str(salida)]


def procesar_documento(
    documento: DocumentoSeleccionado,
    ruta_assets: Path,
    ruta_salida: Path,
    trabajadores: int,
) -> ResultadoOcr:
    """Aplica el OCR que necesite el documento (o ninguno) y devuelve su resultado."""
    original = ruta_assets / documento.ruta_relativa
    modo = elegir_modo_ocr(documento)

    if modo in (ModoOcr.NO_APLICA, ModoOcr.NO_NECESARIO):
        return ResultadoOcr(documento.ruta_relativa, modo, EstadoOcr.OMITIDO, original)

    destino = ruta_salida / documento.ruta_relativa
    if destino.exists():  # permite reanudar una corrida interrumpida
        return ResultadoOcr(documento.ruta_relativa, modo, EstadoOcr.YA_EXISTIA, destino)

    # Se escribe primero en un temporal: si el proceso se interrumpe, no queda un PDF a medias
    # con el nombre final que la siguiente corrida confundiría con uno terminado.
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    inicio = time.perf_counter()
    proceso = subprocess.run(
        construir_comando(modo, original, temporal, trabajadores),
        capture_output=True,
        text=True,
        check=False,
    )
    segundos = round(time.perf_counter() - inicio, 1)

    if proceso.returncode != 0:
        temporal.unlink(missing_ok=True)
        ultimas = proceso.stderr.strip().splitlines()[-LINEAS_ERROR_A_GUARDAR:]
        mensaje = " / ".join(ultimas) or f"código de salida {proceso.returncode}"
        logger.error("OCR falló en %s: %s", documento.ruta_relativa, mensaje)
        return ResultadoOcr(
            documento.ruta_relativa, modo, EstadoOcr.ERROR, original, segundos, mensaje
        )

    temporal.replace(destino)
    return ResultadoOcr(documento.ruta_relativa, modo, EstadoOcr.PROCESADO, destino, segundos)


def ejecutar_ocr(
    documentos: Sequence[DocumentoSeleccionado],
    ruta_assets: Path,
    ruta_salida: Path,
    trabajadores: int,
) -> list[ResultadoOcr]:
    """Procesa los documentos uno por uno (``ocrmypdf`` ya usa varios núcleos por documento)."""
    resultados: list[ResultadoOcr] = []
    for numero, documento in enumerate(documentos, start=1):
        resultado = procesar_documento(documento, ruta_assets, ruta_salida, trabajadores)
        logger.info(
            "[%d/%d] %-12s %-11s %6.1f s  %s",
            numero,
            len(documentos),
            resultado.modo,
            resultado.estado,
            resultado.segundos,
            documento.ruta_relativa.name,
        )
        resultados.append(resultado)
    return resultados


def escribir_manifiesto(resultados: Sequence[ResultadoOcr], destino: Path) -> None:
    """Escribe ``manifiesto.csv``: la entrada del paso de conversión a Markdown."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(("ruta_relativa", "modo", "estado", "ruta_fuente", "segundos", "mensaje"))
        for r in resultados:
            escritor.writerow(
                (r.ruta_relativa, r.modo, r.estado, r.ruta_fuente, r.segundos, r.mensaje)
            )


def leer_documentos_con_ocr(ruta_manifiesto: Path) -> frozenset[str]:
    """Rutas de los documentos a los que sí se aplicó OCR (según el manifiesto)."""
    con_ocr = {ModoOcr.COMPLETAR, ModoOcr.REHACER}
    terminados = {EstadoOcr.PROCESADO, EstadoOcr.YA_EXISTIA}
    with ruta_manifiesto.open(encoding="utf-8-sig", newline="") as archivo:
        return frozenset(
            normalizar_ruta(fila["ruta_relativa"])
            for fila in csv.DictReader(archivo)
            if fila["modo"] in con_ocr and fila["estado"] in terminados
        )
