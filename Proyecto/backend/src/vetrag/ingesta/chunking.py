"""Paso 4 de la F2: dividir cada documento limpio en *chunks* para vectorizarlos.

1. El Markdown se lee como una lista de **bloques** (título, párrafo o tabla), cada uno con su
   página (de las marcas ``<!-- pagina: N -->``) y su **ruta de títulos** (capítulo > sección).
2. Los bloques se juntan en chunks de ~``TOKENS_OBJETIVO`` tokens **sin cambiar de sección**,
   cortando entre párrafos. Las secciones muy cortas se unen con la siguiente.
3. Un párrafo demasiado largo se corta por oraciones; una tabla demasiado larga, por filas,
   repitiendo el encabezado. Nunca se corta a mitad de una oración ni de una fila.
4. Cada chunk empieza con el final del anterior (``TOKENS_TRASLAPE``) para no perder contexto.
5. El texto que se vectoriza lleva un **encabezado de contexto** (documento, especialidad y
   sección), para que el vector "sepa" de qué libro y tema es el fragmento.
"""

import hashlib
import json
import logging
import re
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from vetrag.clasificacion.detectores import detectar_idioma
from vetrag.clasificacion.modelos import Idioma
from vetrag.ingesta.conversion import PATRON_MARCA_PAGINA, ruta_markdown
from vetrag.ingesta.limpieza import separar_cabecera
from vetrag.ingesta.seleccion import DocumentoSeleccionado
from vetrag.ingesta.unidades import buscar_unidades_desconocidas

logger = logging.getLogger(__name__)

# Aproximación: ~4 caracteres por token en español e inglés. Sirve para dar tamaño a los
# chunks; el conteo exacto (para el límite de tokens gratuitos) se hace al vectorizar.
CARACTERES_POR_TOKEN = 4
TOKENS_OBJETIVO = 800
TOKENS_TRASLAPE = 100
TOKENS_MINIMO_SECCION = 100  # secciones más cortas se unen con la siguiente
TOKENS_MINIMO_CHUNK = 20  # chunks más cortos (restos, basura) se descartan
LONGITUD_MAXIMA_TITULO = 150  # un "título" más largo es un párrafo mal detectado

_PATRON_TITULO = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
# Fin de oración: ".", "!" o "?" seguidos de espacio y de algo que empieza oración. No se corta
# en ":" ni ";" para no separar "Dosis:" de su valor.
_PATRON_FIN_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9\"(])")


class TipoBloque(StrEnum):
    """Unidades mínimas del documento: nunca se cortan por dentro (salvo si son enormes)."""

    TITULO = "titulo"
    PARRAFO = "parrafo"
    TABLA = "tabla"


@dataclass(frozen=True, slots=True)
class Bloque:
    """Un título, párrafo o tabla, con su página y la ruta de títulos en la que está."""

    tipo: TipoBloque
    texto: str
    pagina: int | None
    ruta_titulos: tuple[str, ...] = ()
    nivel: int = 0  # solo para títulos: 1 = "#", 2 = "##"…


@dataclass(slots=True)
class Chunk:
    """Un fragmento listo para vectorizar."""

    id: str
    documento: str
    fuente: str
    especialidad: str
    idioma: str
    ruta_titulos: list[str]
    pagina_inicio: int | None
    pagina_fin: int | None
    tokens: int
    texto: str
    texto_para_embedding: str
    unidades_dudosas: list[str] = field(default_factory=list)


def contar_tokens(texto: str) -> int:
    """Tokens aproximados (ver ``CARACTERES_POR_TOKEN``)."""
    return max(1, len(texto) // CARACTERES_POR_TOKEN) if texto.strip() else 0


# --- 1. Del Markdown a bloques ------------------------------------------------------------


def leer_cabecera(markdown: str) -> dict[str, str | int | None]:
    """Lee la cabecera YAML que escribió la conversión (cada valor es JSON)."""
    cabecera, _ = separar_cabecera(markdown)
    metadatos: dict[str, str | int | None] = {}
    for linea in cabecera.strip().strip("-").strip().splitlines():
        clave, _, valor = linea.partition(":")
        if clave.strip():
            metadatos[clave.strip()] = json.loads(valor.strip())
    return metadatos


def _es_tabla(linea: str) -> bool:
    return linea.lstrip().startswith("|")


def leer_bloques(cuerpo: str) -> list[Bloque]:
    """Convierte el cuerpo del Markdown en bloques con página y ruta de títulos."""
    bloques: list[Bloque] = []
    pagina: int | None = None
    ruta: list[tuple[int, str]] = []  # pila de (nivel, título)
    pendiente: list[str] = []  # líneas del bloque que se está armando
    tipo_pendiente = TipoBloque.PARRAFO

    def cerrar() -> None:
        nonlocal pendiente
        texto = "\n".join(pendiente).strip()
        if texto:
            bloques.append(Bloque(tipo_pendiente, texto, pagina, tuple(t for _, t in ruta)))
        pendiente = []

    for linea in cuerpo.splitlines():
        marca = PATRON_MARCA_PAGINA.fullmatch(linea.strip())
        if marca:
            cerrar()
            pagina = int(marca.group(1))
            continue
        if not linea.strip():
            cerrar()
            continue
        titulo = _PATRON_TITULO.match(linea)
        if titulo and len(titulo.group(2)) <= LONGITUD_MAXIMA_TITULO:
            cerrar()
            nivel, texto = len(titulo.group(1)), titulo.group(2).strip("*_ ")
            while ruta and ruta[-1][0] >= nivel:
                ruta.pop()
            ruta.append((nivel, texto))
            bloques.append(
                Bloque(TipoBloque.TITULO, texto, pagina, tuple(t for _, t in ruta), nivel)
            )
            continue
        tipo_linea = TipoBloque.TABLA if _es_tabla(linea) else TipoBloque.PARRAFO
        if pendiente and tipo_linea is not tipo_pendiente:
            cerrar()
        tipo_pendiente = tipo_linea
        pendiente.append(linea.rstrip())
    cerrar()
    return bloques


# --- 2. Partir bloques demasiado grandes --------------------------------------------------


def partir_parrafo(texto: str, maximo: int = TOKENS_OBJETIVO) -> list[str]:
    """Corta un párrafo largo por oraciones, en pedazos de hasta ``maximo`` tokens."""
    pedazos: list[str] = []
    actual = ""
    for oracion in _PATRON_FIN_ORACION.split(texto):
        candidato = f"{actual} {oracion}".strip()
        if actual and contar_tokens(candidato) > maximo:
            pedazos.append(actual)
            actual = oracion
        else:
            actual = candidato
    if actual:
        pedazos.append(actual)
    # Una "oración" enorme sin puntos (texto de OCR) se corta por longitud.
    limite = maximo * CARACTERES_POR_TOKEN
    return [p[i : i + limite] for p in pedazos for i in range(0, len(p), limite)]


def partir_tabla(texto: str, maximo: int = TOKENS_OBJETIVO) -> list[str]:
    """Corta una tabla larga por filas, repitiendo el encabezado en cada pedazo."""
    filas = texto.splitlines()
    separador = next((i for i, f in enumerate(filas) if re.fullmatch(r"\|[\s:|-]+\|?", f)), None)
    encabezado = filas[: separador + 1] if separador is not None else []
    cuerpo = filas[len(encabezado) :]
    pedazos: list[str] = []
    actual: list[str] = []
    for fila in cuerpo:
        if actual and contar_tokens("\n".join([*encabezado, *actual, fila])) > maximo:
            pedazos.append("\n".join([*encabezado, *actual]))
            actual = []
        actual.append(fila)
    if actual or not pedazos:
        pedazos.append("\n".join([*encabezado, *actual]))
    return pedazos


def _dividir_bloque(bloque: Bloque) -> list[Bloque]:
    if contar_tokens(bloque.texto) <= TOKENS_OBJETIVO:
        return [bloque]
    partir = partir_tabla if bloque.tipo is TipoBloque.TABLA else partir_parrafo
    return [
        Bloque(bloque.tipo, pedazo, bloque.pagina, bloque.ruta_titulos)
        for pedazo in partir(bloque.texto)
    ]


# --- 3. Juntar bloques en chunks ----------------------------------------------------------


def _traslape(bloques: Sequence[Bloque]) -> list[Bloque]:
    """Los últimos bloques del chunk anterior que caben en ``TOKENS_TRASLAPE``.

    Si el último bloque es más largo, se toman sus últimas oraciones. Las tablas no se
    repiten: un pedazo de tabla sin su encabezado confundiría más de lo que ayuda.
    """
    ultimo = bloques[-1]
    if ultimo.tipo is TipoBloque.TABLA:
        return []
    if contar_tokens(ultimo.texto) <= TOKENS_TRASLAPE:
        return [ultimo]
    oraciones = _PATRON_FIN_ORACION.split(ultimo.texto)
    cola: list[str] = []
    while oraciones and contar_tokens(" ".join([oraciones[-1], *cola])) <= TOKENS_TRASLAPE:
        cola.insert(0, oraciones.pop())
    if not cola:
        return []
    return [Bloque(TipoBloque.PARRAFO, " ".join(cola), ultimo.pagina, ultimo.ruta_titulos)]


def agrupar_bloques(bloques: Sequence[Bloque]) -> Iterator[list[Bloque]]:
    """Agrupa bloques en chunks de ~``TOKENS_OBJETIVO`` tokens, sin mezclar secciones.

    Los títulos no forman chunks propios: su texto ya viaja en la ruta de títulos (y en el
    encabezado de contexto), así que se usan solo para saber dónde empieza una sección.
    """
    actual: list[Bloque] = []
    tokens = 0
    tiene_contenido_nuevo = False  # para no emitir un chunk hecho solo de traslape

    def emitir() -> Iterator[list[Bloque]]:
        nonlocal actual, tokens, tiene_contenido_nuevo
        if actual and tiene_contenido_nuevo:
            yield actual
            actual = _traslape(actual)
        else:
            actual = []
        tokens = sum(contar_tokens(b.texto) for b in actual)
        tiene_contenido_nuevo = False

    for bloque in (pedazo for b in bloques for pedazo in _dividir_bloque(b)):
        if bloque.tipo is TipoBloque.TITULO:
            # Nueva sección: se cierra el chunk, salvo que sea tan corto que conviene unirlo.
            if tokens >= TOKENS_MINIMO_SECCION:
                yield from emitir()
            if not tiene_contenido_nuevo:
                actual = []  # el traslape nunca cruza a otra sección
                tokens = 0
            continue
        tamano = contar_tokens(bloque.texto)
        if tiene_contenido_nuevo and tokens + tamano > TOKENS_OBJETIVO:
            yield from emitir()
        actual.append(bloque)
        tokens += tamano
        tiene_contenido_nuevo = True
    if actual and tiene_contenido_nuevo:
        yield actual


# --- 4. Chunk final -------------------------------------------------------------------------


def titulo_legible(nombre: str) -> str:
    """``Anatomia+de+los+Animales`` → ``Anatomia de los Animales``."""
    return re.sub(r"\s+", " ", re.sub(r"[+_]", " ", nombre)).strip()


def construir_encabezado(documento: str, especialidad: str, ruta: Sequence[str]) -> str:
    """Encabezado de contexto que se antepone al texto que se vectoriza."""
    lineas = [f"Documento: {documento} | Especialidad: {especialidad}"]
    if ruta:
        lineas.append("Sección: " + " > ".join(ruta))
    return "\n".join(lineas)


def construir_chunk(
    bloques: Sequence[Bloque], metadatos: dict[str, str | int | None], indice: int
) -> Chunk:
    """Arma el chunk con sus metadatos a partir de sus bloques."""
    texto = "\n\n".join(b.texto for b in bloques)
    fuente = str(metadatos.get("fuente") or "")
    documento = titulo_legible(str(metadatos.get("documento") or Path(fuente).stem))
    especialidad = str(metadatos.get("especialidad") or "")
    # La ruta del último bloque: el traslape nunca cruza de sección, y si se unieron secciones
    # cortas, la última es la que aporta más contenido.
    ruta = list(bloques[-1].ruta_titulos)
    paginas = [b.pagina for b in bloques if b.pagina is not None]
    idioma = detectar_idioma(texto)
    if idioma is Idioma.DESCONOCIDO:
        idioma = Idioma(str(metadatos.get("idioma") or Idioma.DESCONOCIDO))
    return Chunk(
        id=hashlib.sha1(f"{fuente}#{indice}".encode()).hexdigest()[:16],
        documento=documento,
        fuente=fuente,
        especialidad=especialidad,
        idioma=idioma,
        ruta_titulos=ruta,
        pagina_inicio=min(paginas) if paginas else None,
        pagina_fin=max(paginas) if paginas else None,
        tokens=contar_tokens(texto),
        texto=texto,
        texto_para_embedding=construir_encabezado(documento, especialidad, ruta)
        + "\n---\n"
        + texto,
        unidades_dudosas=buscar_unidades_desconocidas(texto),
    )


def dividir_documento(markdown: str) -> list[Chunk]:
    """Divide un documento limpio en chunks."""
    metadatos = leer_cabecera(markdown)
    _, cuerpo = separar_cabecera(markdown)
    grupos = agrupar_bloques(leer_bloques(cuerpo))
    chunks = [construir_chunk(grupo, metadatos, i) for i, grupo in enumerate(grupos)]
    return [c for c in chunks if c.tokens >= TOKENS_MINIMO_CHUNK]


# --- 5. Todo el corpus ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResumenChunking:
    """Totales del corpus para el reporte."""

    documentos: int
    documentos_sin_chunks: int
    chunks: int
    duplicados_descartados: int
    tokens: int
    tokens_para_embedding: int
    chunks_con_unidades_dudosas: int


def ejecutar_chunking(
    documentos: Sequence[DocumentoSeleccionado], ruta_limpio: Path, destino: Path
) -> ResumenChunking:
    """Divide todos los documentos y escribe ``chunks.jsonl`` (un chunk por línea).

    Los chunks con texto idéntico (libros repetidos con otro nombre, páginas iguales en
    varias revistas) se guardan una sola vez.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    vistos: set[str] = set()
    total = sin_chunks = duplicados = tokens = tokens_embedding = dudosos = 0
    with destino.open("w", encoding="utf-8") as salida:
        for numero, documento in enumerate(documentos, start=1):
            origen = ruta_markdown(ruta_limpio, documento.ruta_relativa)
            if not origen.exists():
                sin_chunks += 1
                continue
            chunks = dividir_documento(origen.read_text(encoding="utf-8"))
            nuevos = 0
            for chunk in chunks:
                huella = hashlib.sha1(" ".join(chunk.texto.split()).lower().encode()).hexdigest()
                if huella in vistos:
                    duplicados += 1
                    continue
                vistos.add(huella)
                salida.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
                nuevos += 1
                tokens += chunk.tokens
                tokens_embedding += contar_tokens(chunk.texto_para_embedding)
                dudosos += bool(chunk.unidades_dudosas)
            total += nuevos
            sin_chunks += nuevos == 0
            logger.info(
                "[%d/%d] %5d chunks  %s", numero, len(documentos), nuevos,
                documento.ruta_relativa.name,
            )  # fmt: skip
    return ResumenChunking(
        documentos=len(documentos),
        documentos_sin_chunks=sin_chunks,
        chunks=total,
        duplicados_descartados=duplicados,
        tokens=tokens,
        tokens_para_embedding=tokens_embedding,
        chunks_con_unidades_dudosas=dudosos,
    )
