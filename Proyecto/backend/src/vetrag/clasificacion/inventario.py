"""Construcción del inventario: recorre ``assets/``, analiza cada archivo y recomienda."""

import hashlib
import logging
import os
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from vetrag.clasificacion import detectores
from vetrag.clasificacion.lector_pdf import leer_muestra
from vetrag.clasificacion.modelos import (
    Idioma,
    RegistroArchivo,
    SenalRuido,
    TipoContenido,
)

logger = logging.getLogger(__name__)

SIN_ESPECIALIDAD = "(sin carpeta)"


def recorrer_archivos(raiz: Path) -> Iterator[Path]:
    """Archivos de ``raiz`` en orden alfabético, sin ocultos (``.DS_Store``) ni los README."""
    for ruta in sorted(raiz.rglob("*")):
        relativa = ruta.relative_to(raiz)
        if any(parte.startswith(".") for parte in relativa.parts):
            continue
        if ruta.is_file() and ruta.name != "README.md":
            yield ruta


def resolver_base_biblioteca(raiz: Path) -> Path:
    """Carpeta desde la que se cuentan las especialidades.

    Si ``raiz`` solo contiene una carpeta (p. ej. ``Mi biblioteca Veterinaria/``), las
    especialidades son las subcarpetas de esa carpeta.
    """
    visibles = [
        hijo
        for hijo in raiz.iterdir()
        if not hijo.name.startswith(".") and hijo.name != "README.md"
    ]
    if len(visibles) == 1 and visibles[0].is_dir():
        return visibles[0]
    return raiz


def calcular_sha256(ruta: Path) -> str:
    """Hash SHA-256 del contenido binario del archivo."""
    with ruta.open("rb") as archivo:
        return hashlib.file_digest(archivo, "sha256").hexdigest()


def analizar_archivo(ruta: Path, raiz: Path, base: Path) -> RegistroArchivo:
    """Analiza un archivo y devuelve su registro, todavía sin duplicados ni recomendación."""
    relativa_base = ruta.relative_to(base)
    especialidad = relativa_base.parts[0] if len(relativa_base.parts) > 1 else SIN_ESPECIALIDAD
    extension = ruta.suffix.lower()
    registro = RegistroArchivo(
        ruta_relativa=ruta.relative_to(raiz),
        especialidad=especialidad,
        extension=extension,
        tamano_bytes=ruta.stat().st_size,
        sha256=calcular_sha256(ruta),
        tipo_contenido=TipoContenido.NO_SOPORTADO,
    )

    if detectores.tiene_nombre_ruido(ruta.stem):
        registro.senales.append(SenalRuido.NOMBRE_RUIDO)
    if detectores.es_nombre_no_descriptivo(ruta.stem):
        registro.senales.append(SenalRuido.NOMBRE_NO_DESCRIPTIVO)

    if extension in detectores.EXTENSIONES_PDF:
        _analizar_pdf(ruta, registro)
    elif extension in detectores.EXTENSIONES_DOCUMENTO:
        registro.tipo_contenido = TipoContenido.DOCUMENTO
    elif extension in detectores.EXTENSIONES_COMPRIMIDAS:
        registro.senales.append(SenalRuido.ARCHIVO_COMPRIMIDO)
    else:
        registro.senales.append(SenalRuido.FORMATO_NO_SOPORTADO)
    return registro


def _analizar_pdf(ruta: Path, registro: RegistroArchivo) -> None:
    """Completa el registro con el tipo de contenido, idioma y calidad del texto del PDF."""
    try:
        muestra = leer_muestra(ruta)
    except Exception as error:  # pypdfium2 lanza varios tipos según el daño del PDF
        logger.warning("No se pudo leer %s: %s", registro.ruta_relativa, error)
        registro.tipo_contenido = TipoContenido.ERROR
        registro.error = str(error)
        registro.senales.append(SenalRuido.ERROR_LECTURA)
        return

    tipo, promedio, proporcion = detectores.clasificar_tipo_contenido(muestra.textos)
    texto = "\n".join(muestra.textos)
    registro.paginas = muestra.paginas
    registro.tipo_contenido = tipo
    registro.caracteres_por_pagina = round(promedio, 1)
    registro.proporcion_paginas_con_texto = round(proporcion, 2)
    registro.muestra_texto = detectores.extraer_muestra_legible(muestra.textos)

    if tipo is not TipoContenido.ESCANEADO:
        registro.idioma = detectores.detectar_idioma(texto)
        calidad = detectores.calcular_calidad_texto(texto)
        registro.calidad_texto = None if calidad is None else round(calidad, 2)
        if calidad is not None and calidad < detectores.CALIDAD_TEXTO_MINIMA:
            registro.senales.append(SenalRuido.TEXTO_BAJA_CALIDAD)
    else:
        registro.idioma = Idioma.DESCONOCIDO  # se sabrá después del OCR

    if muestra.paginas <= detectores.MAX_PAGINAS_POCAS:
        registro.senales.append(SenalRuido.POCAS_PAGINAS)


def marcar_duplicados(registros: list[RegistroArchivo]) -> None:
    """Marca como duplicados los archivos con el mismo contenido binario.

    Se conserva como original el que no tiene sufijo de copia ``(n)`` y tiene la ruta más
    corta; el resto recibe la señal ``DUPLICADO`` y apunta al original.
    """
    por_hash: defaultdict[str, list[RegistroArchivo]] = defaultdict(list)
    for registro in registros:
        por_hash[registro.sha256].append(registro)

    for grupo in por_hash.values():
        if len(grupo) < 2:
            continue
        grupo.sort(
            key=lambda r: (
                bool(detectores.PATRON_SUFIJO_COPIA.search(r.ruta_relativa.stem)),
                len(str(r.ruta_relativa)),
                str(r.ruta_relativa),
            )
        )
        original, *copias = grupo
        for copia in copias:
            copia.duplicado_de = original.ruta_relativa
            copia.senales.append(SenalRuido.DUPLICADO)


def construir_inventario(
    raiz: Path,
    trabajadores: int | None = None,
    al_avanzar: Callable[[int, int], None] | None = None,
) -> list[RegistroArchivo]:
    """Analiza todos los archivos de ``raiz`` en paralelo y devuelve el inventario completo.

    Args:
        raiz: carpeta ``assets/``.
        trabajadores: procesos en paralelo (por defecto, uno por núcleo).
        al_avanzar: función opcional que recibe ``(procesados, total)``.
    """
    base = resolver_base_biblioteca(raiz)
    rutas = list(recorrer_archivos(raiz))
    total = len(rutas)
    logger.info("Analizando %d archivos de %s", total, raiz)

    registros: list[RegistroArchivo] = []
    with ProcessPoolExecutor(max_workers=trabajadores or os.cpu_count()) as ejecutor:
        resultados = ejecutor.map(
            analizar_archivo, rutas, [raiz] * total, [base] * total, chunksize=4
        )
        for procesados, registro in enumerate(resultados, start=1):
            registros.append(registro)
            if al_avanzar:
                al_avanzar(procesados, total)

    marcar_duplicados(registros)
    for registro in registros:
        registro.recomendacion = detectores.recomendar(registro.senales)
    return registros
