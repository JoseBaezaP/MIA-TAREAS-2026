"""Tipos de datos de la fase de clasificación."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class TipoContenido(StrEnum):
    """Qué tipo de contenido tiene un archivo, visto desde la extracción de texto."""

    TEXTO = "texto"
    ESCANEADO = "escaneado"
    MIXTO = "mixto"
    DOCUMENTO = "documento"  # Office, EPUB, HTML: se convierten en la F2
    NO_SOPORTADO = "no_soportado"
    ERROR = "error"


class Idioma(StrEnum):
    """Idioma predominante del texto."""

    ESPANOL = "es"
    INGLES = "en"
    MIXTO = "mixto"
    DESCONOCIDO = "desconocido"


class SenalRuido(StrEnum):
    """Motivos por los que un archivo podría no aportar al RAG."""

    NOMBRE_RUIDO = "nombre_ruido"
    NOMBRE_NO_DESCRIPTIVO = "nombre_no_descriptivo"
    DUPLICADO = "duplicado"
    POCAS_PAGINAS = "pocas_paginas"
    TEXTO_BAJA_CALIDAD = "texto_baja_calidad"
    FORMATO_NO_SOPORTADO = "formato_no_soportado"
    ARCHIVO_COMPRIMIDO = "archivo_comprimido"
    ERROR_LECTURA = "error_lectura"


class Recomendacion(StrEnum):
    """Recomendación automática; la decisión final se toma a mano."""

    CONSERVAR = "conservar"
    REVISAR = "revisar"
    DESCARTAR = "descartar"


@dataclass(frozen=True, slots=True)
class MuestraPdf:
    """Número de páginas de un PDF y el texto de las páginas muestreadas."""

    paginas: int
    textos: tuple[str, ...]


@dataclass(slots=True)
class RegistroArchivo:
    """Una fila del inventario: todo lo que se sabe de un archivo de ``assets/``."""

    ruta_relativa: Path
    especialidad: str
    extension: str
    tamano_bytes: int
    sha256: str
    tipo_contenido: TipoContenido
    paginas: int | None = None
    caracteres_por_pagina: float | None = None
    proporcion_paginas_con_texto: float | None = None
    idioma: Idioma = Idioma.DESCONOCIDO
    calidad_texto: float | None = None
    muestra_texto: str = ""
    error: str | None = None
    duplicado_de: Path | None = None
    senales: list[SenalRuido] = field(default_factory=list)
    recomendacion: Recomendacion = Recomendacion.CONSERVAR
