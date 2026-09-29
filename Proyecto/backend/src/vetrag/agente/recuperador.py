"""Búsqueda semántica en pgvector: un **puerto** y su adaptador (Voyage + PostgreSQL)."""

from typing import Protocol, cast

from psycopg_pool import ConnectionPool
from voyageai.client import Client as ClienteVoyage

from vetrag.agente.estado import Fragmento
from vetrag.base_datos.repositorio_chunks import vector_a_texto


def crear_pool(url: str, maximo: int = 5) -> ConnectionPool:
    """Pool de conexiones en modo autocommit (ver ``base_datos/conexion.py``)."""
    return ConnectionPool(url, min_size=1, max_size=maximo, kwargs={"autocommit": True}, open=True)


class Recuperador(Protocol):
    """Lo que el agente necesita para buscar en la biblioteca."""

    def buscar(self, consulta: str, cantidad: int) -> list[Fragmento]: ...


class RecuperadorPgvector:
    """Vectoriza la consulta con Voyage (``input_type="query"``) y busca los chunks más cercanos
    por similitud coseno usando el índice HNSW.

    Usa un *pool* de conexiones: en la API llegan varias preguntas a la vez y una conexión de
    PostgreSQL no se puede compartir entre ellas; cada búsqueda toma una del pool y la devuelve.
    """

    _SQL = """
        SELECT id, documento, especialidad, ruta_titulos, pagina_inicio, pagina_fin, texto,
               1 - (embedding <=> %(vector)s::vector) AS similitud, unidades_dudosas
        FROM chunks
        ORDER BY embedding <=> %(vector)s::vector
        LIMIT %(cantidad)s
    """

    def __init__(
        self,
        pool: ConnectionPool,
        api_key_voyage: str,
        modelo_embedding: str,
    ) -> None:
        self._pool = pool
        self._voyage = ClienteVoyage(api_key=api_key_voyage)
        self._modelo = modelo_embedding

    def buscar(self, consulta: str, cantidad: int) -> list[Fragmento]:
        vector = self._voyage.embed([consulta], model=self._modelo, input_type="query")
        with self._pool.connection() as conexion:
            filas = conexion.execute(
                self._SQL,
                {"vector": vector_a_texto(vector.embeddings[0]), "cantidad": cantidad},
            ).fetchall()
        return [
            Fragmento(
                id=str(f[0]),
                documento=str(f[1]),
                especialidad=str(f[2]),
                ruta_titulos=tuple(cast(list[str], f[3])),
                pagina_inicio=f[4],
                pagina_fin=f[5],
                texto=str(f[6]),
                similitud=float(f[7]),
                unidades_dudosas=tuple(cast(list[str], f[8])),
            )
            for f in filas
        ]
