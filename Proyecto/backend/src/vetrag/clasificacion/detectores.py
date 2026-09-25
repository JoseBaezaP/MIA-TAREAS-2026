"""Detectores de señales: funciones puras que no leen archivos, para probarlas fácilmente."""

import re
import unicodedata
from collections.abc import Iterable, Sequence

from vetrag.clasificacion.modelos import Idioma, Recomendacion, SenalRuido, TipoContenido

# --- Umbrales -------------------------------------------------------------------------
MIN_CARACTERES_PAGINA_CON_TEXTO = 200  # una página de libro típica tiene 2,000-3,000
PROPORCION_MIN_TEXTO = 0.8  # >= 80 % de páginas con texto → "texto"
PROPORCION_MAX_ESCANEADO = 0.2  # <= 20 % de páginas con texto → "escaneado"
MIN_PALABRAS_PARA_IDIOMA = 20
PROPORCION_IDIOMA_DOMINANTE = 0.8
CALIDAD_TEXTO_MINIMA = 0.7  # calibrado con el corpus: OCR dañado ≈ 0.5-0.65, texto sano > 0.85
MAX_PAGINAS_POCAS = 2

# --- Extensiones ----------------------------------------------------------------------
EXTENSIONES_PDF = frozenset({".pdf"})
EXTENSIONES_DOCUMENTO = frozenset(
    {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".rtf", ".epub", ".html"}
)
EXTENSIONES_COMPRIMIDAS = frozenset({".zip", ".rar", ".7z"})

# --- Nombres ---------------------------------------------------------------------------
PALABRAS_RUIDO = (
    "certificado",
    "constancia",
    "convocatoria",
    "calendario",
    "peluqueria",
    "estetica canina",
    "factura",
    "recibo",
    "curriculum",
    "inscripcion",
    "horario",
)
NOMBRES_GENERICOS = frozenset(
    {"doc", "documento", "document", "archivo", "file", "descarga", "download", "scan"}
)
LONGITUD_MIN_NOMBRE_HASH = 16

# Palabras muy frecuentes y exclusivas de cada idioma (se omiten las compartidas, como "a").
PALABRAS_INDICADORAS_ES = frozenset(
    (
        "de la que el en los del las por con una para es se su al lo como más pero sus le ya "
        "fue este ha porque esta son entre cuando muy sin sobre también hasta hay donde desde "
        "todo nos durante todos uno les ni contra otros ese eso ante ellos esto antes algunos "
        "unos otro otras otra tanto esa estos mucho nada muchos cual poco ella estas algunas "
        "puede pueden así debe animales perro gato"
    ).split()
)
PALABRAS_INDICADORAS_EN = frozenset(
    (
        "the of and to in is that for it with as was on are be by this from at or an which "
        "have not has but were their its can been these also more may other than such into "
        "some only when there they all between after both each most used should animals dog "
        "cat"
    ).split()
)

_PATRON_PALABRA = re.compile(r"[a-záéíóúüñ]+")
_PATRON_PALABRA_VALIDA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,25}|\d+([.,]\d+)?")
PATRON_SUFIJO_COPIA = re.compile(r"\s*\(\d+\)$")
_PUNTUACION = ".,;:()[]{}\"'¿?¡!«»-–—%/"  # noqa: RUF001 - guiones largos a propósito


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con ``_``, ``-`` y ``.`` convertidos en espacios."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return re.sub(r"[_\-.\s]+", " ", sin_acentos.lower()).strip()


def tiene_nombre_ruido(nombre: str) -> bool:
    """Indica si el nombre del archivo sugiere un documento administrativo o ajeno al tema."""
    normalizado = normalizar(nombre)
    return any(palabra in normalizado for palabra in PALABRAS_RUIDO)


def es_nombre_no_descriptivo(nombre: str) -> bool:
    """Detecta nombres que no dicen de qué trata el documento (solo números, hash, genéricos).

    ``nombre`` es el nombre sin extensión; se ignoran sufijos de copia como ``(1)``.
    """
    base = PATRON_SUFIJO_COPIA.sub("", nombre).strip()
    if not base or base.isdigit() or normalizar(base) in NOMBRES_GENERICOS:
        return True
    parece_hash = (
        len(base) >= LONGITUD_MIN_NOMBRE_HASH
        and base.isalnum()
        and any(c.isdigit() for c in base)
        and any(c.isalpha() for c in base)
    )
    return parece_hash


def detectar_idioma(texto: str) -> Idioma:
    """Idioma predominante según la proporción de palabras indicadoras de cada idioma."""
    palabras = _PATRON_PALABRA.findall(texto.lower())
    espanol = sum(1 for p in palabras if p in PALABRAS_INDICADORAS_ES)
    ingles = sum(1 for p in palabras if p in PALABRAS_INDICADORAS_EN)
    total = espanol + ingles
    if total < MIN_PALABRAS_PARA_IDIOMA:
        return Idioma.DESCONOCIDO
    if espanol / total >= PROPORCION_IDIOMA_DOMINANTE:
        return Idioma.ESPANOL
    if ingles / total >= PROPORCION_IDIOMA_DOMINANTE:
        return Idioma.INGLES
    return Idioma.MIXTO


def calcular_calidad_texto(texto: str) -> float | None:
    """Proporción de *tokens* que son palabras o números válidos (0 a 1).

    Un OCR antiguo o dañado produce secuencias como ``l1I|:~`` que bajan este valor.
    Devuelve ``None`` si no hay texto que evaluar.
    """
    tokens = [t.strip(_PUNTUACION) for t in texto.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return None
    validos = sum(1 for t in tokens if _PATRON_PALABRA_VALIDA.fullmatch(t))
    return validos / len(tokens)


def clasificar_tipo_contenido(textos: Sequence[str]) -> tuple[TipoContenido, float, float]:
    """Clasifica un PDF según cuántas de sus páginas muestreadas tienen texto.

    Returns:
        Tupla ``(tipo, caracteres promedio por página, proporción de páginas con texto)``.
    """
    if not textos:
        return TipoContenido.ESCANEADO, 0.0, 0.0
    caracteres = [len(t.strip()) for t in textos]
    promedio = sum(caracteres) / len(caracteres)
    con_texto = sum(1 for c in caracteres if c >= MIN_CARACTERES_PAGINA_CON_TEXTO)
    proporcion = con_texto / len(caracteres)
    if proporcion >= PROPORCION_MIN_TEXTO:
        tipo = TipoContenido.TEXTO
    elif proporcion <= PROPORCION_MAX_ESCANEADO:
        tipo = TipoContenido.ESCANEADO
    else:
        tipo = TipoContenido.MIXTO
    return tipo, promedio, proporcion


def extraer_muestra_legible(textos: Iterable[str], longitud: int = 200) -> str:
    """Fragmento de la página con más texto, en una sola línea, para revisar a mano."""
    mejor = max(textos, key=lambda t: len(t.strip()), default="")
    return " ".join(mejor.split())[:longitud]


def recomendar(senales: Iterable[SenalRuido]) -> Recomendacion:
    """Recomendación automática a partir de las señales detectadas."""
    conjunto = set(senales)
    descartar = {
        SenalRuido.NOMBRE_RUIDO,
        SenalRuido.DUPLICADO,
        SenalRuido.FORMATO_NO_SOPORTADO,
    }
    if conjunto & descartar:
        return Recomendacion.DESCARTAR
    if conjunto:
        return Recomendacion.REVISAR
    return Recomendacion.CONSERVAR
