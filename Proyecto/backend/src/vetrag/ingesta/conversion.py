"""Paso 2 de la F2: conversión de cada documento a Markdown con ``anydoc``.

Los PDFs se convierten **página por página** para poder marcar de qué página viene cada
texto (anydoc no lo indica si se le da el PDF completo). Entre página y página se inserta
un comentario invisible ``<!-- pagina: N -->`` que el chunking usará para citar la fuente.
"""

import csv
import io
import json
import logging
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import anydoc
import pypdfium2 as pdfium

from vetrag.clasificacion.modelos import TipoContenido
from vetrag.ingesta.seleccion import DocumentoSeleccionado, normalizar_ruta

logger = logging.getLogger(__name__)

MARCA_PAGINA = "<!-- pagina: {numero} -->"
PATRON_MARCA_PAGINA = re.compile(r"<!-- pagina: (\d+) -->")


class EstadoConversion(StrEnum):
    """Resultado del paso para un documento."""

    CONVERTIDO = "convertido"
    YA_EXISTIA = "ya_existia"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PaginasConvertidas:
    """Markdown de cada página, cuántas quedaron vacías y cuántas usaron el plan B."""

    textos: tuple[str, ...]
    vacias: int
    texto_plano: int  # páginas que anydoc rechazó y se leyeron como texto plano


@dataclass(frozen=True, slots=True)
class ResultadoConversion:
    """Una fila del manifiesto de conversión."""

    ruta_relativa: Path
    estado: EstadoConversion
    ruta_markdown: Path | None
    paginas: int | None = None
    paginas_vacias: int = 0
    paginas_texto_plano: int = 0
    caracteres: int = 0
    segundos: float = 0.0
    mensaje: str = ""


def leer_manifiesto_ocr(ruta_manifiesto: Path) -> dict[str, Path]:
    """``ruta_relativa → ruta_fuente`` del manifiesto del paso de OCR."""
    with ruta_manifiesto.open(encoding="utf-8-sig", newline="") as archivo:
        return {
            normalizar_ruta(fila["ruta_relativa"]): Path(fila["ruta_fuente"])
            for fila in csv.DictReader(archivo)
        }


def separar_paginas(ruta_pdf: Path) -> list[bytes]:
    """Divide un PDF en PDFs de una sola página (en memoria)."""
    documento = pdfium.PdfDocument(ruta_pdf)
    try:
        paginas: list[bytes] = []
        for indice in range(len(documento)):
            nuevo = pdfium.PdfDocument.new()
            try:
                nuevo.import_pages(documento, [indice])
                memoria = io.BytesIO()
                nuevo.save(memoria)
                paginas.append(memoria.getvalue())
            finally:
                nuevo.close()
        return paginas
    finally:
        documento.close()


def extraer_texto_plano(pagina_pdf: bytes) -> str:
    """Texto de una página con ``pypdfium2`` (sin formato Markdown)."""
    documento = pdfium.PdfDocument(pagina_pdf)
    try:
        capa_texto = documento[0].get_textpage()
        return str(capa_texto.get_text_range()).strip()
    finally:
        documento.close()


def convertir_paginas(paginas_pdf: Sequence[bytes]) -> PaginasConvertidas:
    """Convierte cada página a Markdown.

    anydoc rechaza algunas páginas que sí tienen texto: en el piloto, páginas con muy poco
    texto (~70-100 caracteres) y alguna imagen, que clasifica como ``ImageBased``. Su regla
    exacta es interna de la librería, así que no se intenta adivinar: **siempre** que anydoc
    rechaza una página, se usa el plan B (texto plano de ``pypdfium2``). Si tampoco hay texto,
    la página queda vacía.
    """
    textos: list[str] = []
    vacias = texto_plano = 0
    for pagina in paginas_pdf:
        try:
            texto = anydoc.to_markdown_bytes(pagina, "pdf").strip()
        except anydoc.ConvertError as error:
            logger.debug("anydoc rechazó la página (%s); se usa texto plano", error)
            texto = extraer_texto_plano(pagina)
            if texto:
                texto_plano += 1
        if not texto:
            vacias += 1
        textos.append(texto)
    return PaginasConvertidas(tuple(textos), vacias, texto_plano)


def unir_paginas(textos: Sequence[str]) -> str:
    """Une el Markdown de las páginas, precedido cada uno por su marca de página."""
    bloques = [
        f"{MARCA_PAGINA.format(numero=numero)}\n{texto}".rstrip()
        for numero, texto in enumerate(textos, start=1)
    ]
    return "\n\n".join(bloques) + "\n"


def construir_front_matter(metadatos: Mapping[str, str | int | None]) -> str:
    """Cabecera YAML con los metadatos del documento.

    Cada valor se escribe con ``json.dumps``: una cadena JSON también es YAML válido, y así
    los ``:`` o comillas de un título no rompen la cabecera.
    """
    lineas = [
        f"{clave}: {json.dumps(valor, ensure_ascii=False)}" for clave, valor in metadatos.items()
    ]
    return "---\n" + "\n".join(lineas) + "\n---\n\n"


def ruta_markdown(ruta_salida: Path, ruta_relativa: Path) -> Path:
    """``libro.pdf`` → ``libro.pdf.md`` (se conserva la extensión para no mezclar un
    ``libro.pdf`` con un ``libro.pptx`` de la misma carpeta)."""
    return ruta_salida / ruta_relativa.with_name(ruta_relativa.name + ".md")


def convertir_documento(
    documento: DocumentoSeleccionado, ruta_fuente: Path, ruta_salida: Path
) -> ResultadoConversion:
    """Convierte un documento a Markdown con su cabecera de metadatos."""
    destino = ruta_markdown(ruta_salida, documento.ruta_relativa)
    if destino.exists():
        return ResultadoConversion(documento.ruta_relativa, EstadoConversion.YA_EXISTIA, destino)

    inicio = time.perf_counter()
    try:
        if documento.tipo_contenido is TipoContenido.DOCUMENTO:
            cuerpo = anydoc.to_markdown(str(ruta_fuente)).strip() + "\n"
            paginas, vacias, plano = None, 0, 0
        else:
            convertidas = convertir_paginas(separar_paginas(ruta_fuente))
            cuerpo = unir_paginas(convertidas.textos)
            paginas, vacias = len(convertidas.textos), convertidas.vacias
            plano = convertidas.texto_plano
    except Exception as error:  # anydoc y pypdfium2 lanzan varios tipos
        logger.error("No se pudo convertir %s: %s", documento.ruta_relativa, error)
        return ResultadoConversion(
            documento.ruta_relativa, EstadoConversion.ERROR, None, mensaje=str(error)
        )

    cabecera = construir_front_matter(
        {
            "documento": documento.ruta_relativa.stem,
            "especialidad": documento.especialidad,
            "idioma": documento.idioma,
            "fuente": str(documento.ruta_relativa),
            "paginas": paginas,
        }
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    temporal.write_text(cabecera + cuerpo, encoding="utf-8")
    temporal.replace(destino)

    return ResultadoConversion(
        ruta_relativa=documento.ruta_relativa,
        estado=EstadoConversion.CONVERTIDO,
        ruta_markdown=destino,
        paginas=paginas,
        paginas_vacias=vacias,
        paginas_texto_plano=plano,
        caracteres=len(cuerpo),
        segundos=round(time.perf_counter() - inicio, 2),
    )


def ejecutar_conversion(
    documentos: Sequence[DocumentoSeleccionado],
    fuentes: Mapping[str, Path],
    ruta_salida: Path,
) -> list[ResultadoConversion]:
    """Convierte cada documento usando el archivo fuente que indicó el paso de OCR."""
    resultados: list[ResultadoConversion] = []
    for numero, documento in enumerate(documentos, start=1):
        fuente = fuentes.get(str(documento.ruta_relativa))
        if fuente is None:
            resultado = ResultadoConversion(
                documento.ruta_relativa,
                EstadoConversion.ERROR,
                None,
                mensaje="No está en el manifiesto del OCR: corre primero el paso 'ocr'",
            )
        else:
            resultado = convertir_documento(documento, fuente, ruta_salida)
        logger.info(
            "[%d/%d] %-10s %5s págs (%s vacías, %s texto plano) %8s car  %s",
            numero,
            len(documentos),
            resultado.estado,
            resultado.paginas if resultado.paginas is not None else "-",
            resultado.paginas_vacias,
            resultado.paginas_texto_plano,
            f"{resultado.caracteres:,}",
            documento.ruta_relativa.name,
        )
        resultados.append(resultado)
    return resultados


def escribir_manifiesto(resultados: Sequence[ResultadoConversion], destino: Path) -> None:
    """Escribe ``manifiesto.csv`` de la conversión: la entrada del paso de limpieza."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            ("ruta_relativa", "estado", "ruta_markdown", "paginas", "paginas_vacias",
             "paginas_texto_plano", "caracteres", "segundos", "mensaje")
        )  # fmt: skip
        for r in resultados:
            escritor.writerow(
                (r.ruta_relativa, r.estado, r.ruta_markdown or "", r.paginas or "",
                 r.paginas_vacias, r.paginas_texto_plano, r.caracteres, r.segundos, r.mensaje)
            )  # fmt: skip
