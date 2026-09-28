"""Paso 5 de la F2: vectorizar los chunks con Voyage AI y guardarlos en pgvector.

Protecciones:

- **Solo el endpoint normal** de Voyage (``embed``), nunca el Batch API: los tokens gratuitos
  no aplican al Batch API.
- **Límite de tokens**: antes de cada lote se revisa cuántos tokens ya reportó Voyage (se
  guardan en la tabla ``uso_voyage``) y se detiene antes de pasar del límite configurado.
- **Reanudable**: los chunks que ya están en la base se saltan.
- **Reintentos** con espera creciente si Voyage responde "demasiadas peticiones" o falla la red.

La lógica no depende de Voyage ni de PostgreSQL directamente: recibe un ``Vectorizador`` y un
``Repositorio`` (dos "puertos"), así las pruebas usan versiones falsas y no gastan tokens.
"""

import json
import logging
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Protocol

import voyageai.error
from voyageai.client import Client as ClienteVoyage

from vetrag.ingesta.chunking import Chunk, contar_tokens
from vetrag.ingesta.seleccion import normalizar_ruta

logger = logging.getLogger(__name__)

MAX_TEXTOS_POR_LOTE = 1_000  # límite de Voyage por petición
# Voyage acepta hasta 320 mil tokens por petición con voyage-4. Como aquí los tokens se
# ESTIMAN (~4 caracteres por token) y en tablas o texto de OCR la cuenta real puede ser 1.6
# veces mayor, se deja margen. Si aun así un lote se pasa, se parte a la mitad.
MAX_TOKENS_ESTIMADOS_POR_LOTE = 150_000
REINTENTOS = 6
ESPERA_INICIAL_SEGUNDOS = 2.0


# --- Puertos: lo que la lógica necesita, sin saber quién lo implementa ----------------------


@dataclass(frozen=True, slots=True)
class ResultadoEmbedding:
    """Vectores de un lote y los tokens que la API reporta haber usado."""

    vectores: list[list[float]]
    tokens: int


class Vectorizador(Protocol):
    """Convierte textos en vectores."""

    modelo: str

    def vectorizar(self, textos: Sequence[str]) -> ResultadoEmbedding: ...


class Repositorio(Protocol):
    """Dónde se guardan los chunks vectorizados."""

    def ids_existentes(self) -> set[str]: ...

    def tokens_usados(self, modelo: str) -> int: ...

    def guardar(
        self,
        chunks: Sequence[Chunk],
        vectores: Sequence[Sequence[float]],
        tokens: int,
        modelo: str,
    ) -> None: ...


# --- Adaptador real: Voyage AI ---------------------------------------------------------------


class VectorizadorVoyage:
    """Vectorizador con la API de Voyage (``input_type="document"`` para los chunks)."""

    def __init__(self, api_key: str, modelo: str) -> None:
        self._cliente = ClienteVoyage(api_key=api_key, max_retries=0)  # reintentos: propios
        self.modelo = modelo

    def vectorizar(self, textos: Sequence[str]) -> ResultadoEmbedding:
        respuesta = self._cliente.embed(
            list(textos),
            model=self.modelo,
            input_type="document",
            truncation=False,  # mejor un error que un chunk recortado sin avisar
        )
        vectores = [[float(x) for x in v] for v in respuesta.embeddings]
        return ResultadoEmbedding(vectores, int(respuesta.total_tokens))


# --- Lógica -------------------------------------------------------------------------------------


def leer_chunks(ruta: Path, fuentes: set[str] | None = None) -> Iterator[Chunk]:
    """Lee ``chunks.jsonl``. Con ``fuentes``, solo los chunks de esos documentos (piloto)."""
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            chunk = Chunk(**json.loads(linea))
            if fuentes is None or normalizar_ruta(chunk.fuente) in fuentes:
                yield chunk


def armar_lotes(
    chunks: Sequence[Chunk],
    max_textos: int = MAX_TEXTOS_POR_LOTE,
    max_tokens: int = MAX_TOKENS_ESTIMADOS_POR_LOTE,
) -> Iterator[list[Chunk]]:
    """Agrupa chunks en lotes que respetan los límites de Voyage por petición."""
    lote: list[Chunk] = []
    tokens = 0
    for chunk in chunks:
        estimados = contar_tokens(chunk.texto_para_embedding)
        if lote and (len(lote) >= max_textos or tokens + estimados > max_tokens):
            yield lote
            lote, tokens = [], 0
        lote.append(chunk)
        tokens += estimados
    if lote:
        yield lote


_ERRORES_TEMPORALES = (
    voyageai.error.RateLimitError,
    voyageai.error.ServiceUnavailableError,
    voyageai.error.ServerError,
    voyageai.error.APIConnectionError,
)


def con_reintentos(
    funcion: Callable[[], ResultadoEmbedding],
    reintentos: int = REINTENTOS,
    espera_inicial: float = ESPERA_INICIAL_SEGUNDOS,
    dormir: Callable[[float], None] = time.sleep,
) -> ResultadoEmbedding:
    """Ejecuta ``funcion``; si falla por un error temporal, espera 2, 4, 8… segundos y reintenta."""
    for intento in range(reintentos + 1):
        try:
            return funcion()
        except _ERRORES_TEMPORALES as error:
            if intento == reintentos:
                raise
            espera = espera_inicial * 2**intento
            logger.warning("Voyage: %s. Reintento en %.0f s", type(error).__name__, espera)
            dormir(espera)
    raise AssertionError("inalcanzable")  # pragma: no cover


def _es_lote_demasiado_grande(error: voyageai.error.InvalidRequestError) -> bool:
    return "max allowed tokens per submitted batch" in str(error)


def vectorizar_lote(
    lote: Sequence[Chunk], vectorizador: Vectorizador
) -> list[tuple[list[Chunk], ResultadoEmbedding]]:
    """Vectoriza un lote. Si Voyage responde que tiene demasiados tokens, lo parte a la mitad
    y vectoriza cada mitad (y así sucesivamente)."""
    textos = [c.texto_para_embedding for c in lote]
    try:
        return [(list(lote), con_reintentos(partial(vectorizador.vectorizar, textos)))]
    except voyageai.error.InvalidRequestError as error:
        if len(lote) == 1 or not _es_lote_demasiado_grande(error):
            raise
        mitad = len(lote) // 2
        logger.info("Lote de %d chunks demasiado grande: se parte en dos", len(lote))
        return vectorizar_lote(lote[:mitad], vectorizador) + vectorizar_lote(
            lote[mitad:], vectorizador
        )


@dataclass(frozen=True, slots=True)
class ResumenVectorizacion:
    """Qué se hizo en esta corrida."""

    pendientes: int
    vectorizados: int
    ya_existian: int
    tokens_usados_en_esta_corrida: int
    tokens_usados_en_total: int
    detenido_por_limite: bool


def ejecutar_vectorizacion(
    chunks: Sequence[Chunk],
    vectorizador: Vectorizador,
    repositorio: Repositorio,
    limite_tokens: int,
) -> ResumenVectorizacion:
    """Vectoriza los chunks que faltan, lote por lote, sin pasar de ``limite_tokens``."""
    existentes = repositorio.ids_existentes()
    pendientes = [c for c in chunks if c.id not in existentes]
    usados_al_inicio = usados = repositorio.tokens_usados(vectorizador.modelo)
    vectorizados = 0
    detenido = False
    lotes = list(armar_lotes(pendientes))
    logger.info(
        "%d chunks pendientes (%d ya estaban) en %d lotes; tokens usados hasta ahora: %s",
        len(pendientes), len(chunks) - len(pendientes), len(lotes), f"{usados:,}",
    )  # fmt: skip

    for numero, lote in enumerate(lotes, start=1):
        # Se estima con un 25 % de margen porque el conteo real solo se conoce después.
        estimados = int(sum(contar_tokens(c.texto_para_embedding) for c in lote) * 1.25)
        if usados + estimados > limite_tokens:
            logger.warning(
                "Se detiene antes del lote %d: %s usados + ~%s estimados > límite %s",
                numero, f"{usados:,}", f"{estimados:,}", f"{limite_tokens:,}",
            )  # fmt: skip
            detenido = True
            break
        for parte, resultado in vectorizar_lote(lote, vectorizador):
            repositorio.guardar(parte, resultado.vectores, resultado.tokens, vectorizador.modelo)
            usados += resultado.tokens
            vectorizados += len(parte)
            logger.info(
                "[%d/%d] %4d chunks, %7s tokens (total %s)",
                numero, len(lotes), len(parte), f"{resultado.tokens:,}", f"{usados:,}",
            )  # fmt: skip

    return ResumenVectorizacion(
        pendientes=len(pendientes),
        vectorizados=vectorizados,
        ya_existian=len(chunks) - len(pendientes),
        tokens_usados_en_esta_corrida=usados - usados_al_inicio,
        tokens_usados_en_total=usados,
        detenido_por_limite=detenido,
    )
