"""Lectura y escritura de la tabla ``chunks`` (el "repositorio" de la base de conocimiento)."""

from collections.abc import Sequence

import psycopg

from vetrag.ingesta.chunking import Chunk


def vector_a_texto(vector: Sequence[float]) -> str:
    """Formato que entiende pgvector: ``[0.1,0.2,…]``."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


class RepositorioChunks:
    """Guarda chunks con su vector y lleva la cuenta de tokens usados en Voyage."""

    def __init__(self, conexion: psycopg.Connection[tuple[object, ...]]) -> None:
        self._conexion = conexion

    def ids_existentes(self) -> set[str]:
        """Ids ya vectorizados (para reanudar sin repetir)."""
        return {str(fila[0]) for fila in self._conexion.execute("SELECT id FROM chunks")}

    def tokens_usados(self, modelo: str) -> int:
        """Tokens que Voyage ya cobró para ``modelo`` (según sus propias respuestas)."""
        fila = self._conexion.execute(
            "SELECT COALESCE(SUM(tokens), 0) FROM uso_voyage WHERE modelo = %s", (modelo,)
        ).fetchone()
        return int(fila[0]) if fila else 0  # type: ignore[call-overload]

    def guardar(
        self,
        chunks: Sequence[Chunk],
        vectores: Sequence[Sequence[float]],
        tokens: int,
        modelo: str,
    ) -> None:
        """Guarda un lote y su consumo de tokens en **una sola transacción**: o se guarda
        todo o nada, así un corte a la mitad no deja el contador desfasado."""
        with self._conexion.transaction(), self._conexion.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO chunks (id, documento, fuente, especialidad, idioma, ruta_titulos,
                    pagina_inicio, pagina_fin, tokens, texto, unidades_dudosas, embedding,
                    modelo_embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (c.id, c.documento, c.fuente, c.especialidad, c.idioma, c.ruta_titulos,
                     c.pagina_inicio, c.pagina_fin, c.tokens, c.texto, c.unidades_dudosas,
                     vector_a_texto(v), modelo)
                    for c, v in zip(chunks, vectores, strict=True)
                ],
            )  # fmt: skip
            cursor.execute(
                "INSERT INTO uso_voyage (modelo, chunks, tokens) VALUES (%s, %s, %s)",
                (modelo, len(chunks), tokens),
            )

    def crear_indice_vectorial(self) -> None:
        """Índice HNSW por similitud coseno. Se crea al final: es más rápido que mantenerlo
        actualizado mientras se insertan miles de filas."""
        self._conexion.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
        self._conexion.commit()

    def contar(self) -> int:
        """Número de chunks guardados."""
        fila = self._conexion.execute("SELECT count(*) FROM chunks").fetchone()
        return int(fila[0]) if fila else 0  # type: ignore[call-overload]
