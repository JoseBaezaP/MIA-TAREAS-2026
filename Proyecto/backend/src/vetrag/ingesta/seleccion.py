"""Qué documentos procesa la F2: los que tienen ``decision = conservar`` en el inventario."""

import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from vetrag.clasificacion.modelos import TipoContenido

DECISION_CONSERVAR = "conservar"


@dataclass(frozen=True, slots=True)
class DocumentoSeleccionado:
    """Lo que la F2 necesita saber de cada documento, tomado del inventario de la F1."""

    ruta_relativa: Path
    especialidad: str
    tipo_contenido: TipoContenido
    idioma: str
    calidad_texto: float | None
    paginas: int | None


def normalizar_ruta(texto: str) -> str:
    """Unifica la forma de los acentos (NFC).

    macOS guarda ``é`` como ``e`` + un acento combinable (dos caracteres, forma NFD) y lo
    escrito a mano suele ser ``é`` (uno solo, NFC). Se ven igual, pero para Python son
    textos distintos.
    """
    return unicodedata.normalize("NFC", texto.strip())


def _entero(valor: str) -> int | None:
    return int(valor) if valor.strip() else None


def _decimal(valor: str) -> float | None:
    return float(valor) if valor.strip() else None


def leer_seleccion(ruta_inventario: Path) -> list[DocumentoSeleccionado]:
    """Documentos del inventario con ``decision = conservar``."""
    with ruta_inventario.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    return [
        DocumentoSeleccionado(
            ruta_relativa=Path(normalizar_ruta(fila["ruta_relativa"])),
            especialidad=normalizar_ruta(fila["especialidad"]),
            tipo_contenido=TipoContenido(fila["tipo_contenido"]),
            idioma=fila["idioma"],
            calidad_texto=_decimal(fila["calidad_texto"]),
            paginas=_entero(fila["paginas"]),
        )
        for fila in filas
        if fila["decision"].strip().lower() == DECISION_CONSERVAR
    ]


def leer_lista_piloto(ruta_lista: Path) -> set[str]:
    """Rutas de la lista del piloto (una por línea; ``#`` inicia un comentario)."""
    lineas = ruta_lista.read_text(encoding="utf-8").splitlines()
    return {
        normalizar_ruta(linea)
        for linea in lineas
        if linea.strip() and not linea.strip().startswith("#")
    }


def filtrar_piloto(
    documentos: list[DocumentoSeleccionado], rutas_piloto: set[str]
) -> list[DocumentoSeleccionado]:
    """Solo los documentos de la lista del piloto.

    Raises:
        ValueError: si alguna ruta del piloto no está entre los documentos conservados.
    """
    elegidos = [d for d in documentos if str(d.ruta_relativa) in rutas_piloto]
    faltantes = rutas_piloto - {str(d.ruta_relativa) for d in elegidos}
    if faltantes:
        raise ValueError(f"No están en el inventario como 'conservar': {sorted(faltantes)}")
    return elegidos
