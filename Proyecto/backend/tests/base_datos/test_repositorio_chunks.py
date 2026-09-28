"""Pruebas del repositorio contra PostgreSQL real.

Solo corren si existe ``VETRAG_TEST_DATABASE_URL`` (una base de pruebas, NUNCA la del
proyecto): crean las tablas en un esquema temporal y lo borran al terminar.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest

from tests.ingesta.test_vectorizacion import chunk
from vetrag.base_datos.conexion import conectar, crear_esquema
from vetrag.base_datos.repositorio_chunks import RepositorioChunks, vector_a_texto

URL = os.environ.get("VETRAG_TEST_DATABASE_URL")


def test_vector_a_texto() -> None:
    assert vector_a_texto([0.1, -2.0, 3.5]) == "[0.1,-2,3.5]"


@pytest.fixture
def conexion() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    if URL is None:
        pytest.skip("sin VETRAG_TEST_DATABASE_URL")
    with conectar(URL) as con:  # la misma conexión que usa el proyecto (autocommit)
        con.execute("DROP SCHEMA IF EXISTS prueba_vetrag CASCADE")
        con.execute("CREATE SCHEMA prueba_vetrag")
        con.execute("SET search_path TO prueba_vetrag, public")
        crear_esquema(con)
        yield con
        con.execute("DROP SCHEMA prueba_vetrag CASCADE")


def test_guardar_y_contar(conexion: psycopg.Connection[tuple[object, ...]]) -> None:
    repositorio = RepositorioChunks(conexion)
    repositorio.guardar([chunk(1), chunk(2)], [[0.1] * 1024, [0.2] * 1024], 1000, "voyage-4")
    assert repositorio.contar() == 2
    assert repositorio.ids_existentes() == {"id1", "id2"}
    assert repositorio.tokens_usados("voyage-4") == 1000


def test_cada_lote_queda_guardado_aunque_el_proceso_falle_despues(
    conexion: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Otra conexión debe ver el lote apenas se guarda, sin esperar al final del proceso."""
    repositorio = RepositorioChunks(conexion)
    repositorio.ids_existentes()  # una consulta antes, como en la vectorización real
    repositorio.guardar([chunk(1)], [[0.1] * 1024], 500, "voyage-4")
    assert URL is not None
    with psycopg.connect(URL) as otra:
        otra.execute("SET search_path TO prueba_vetrag, public")
        fila = otra.execute("SELECT count(*) FROM chunks").fetchone()
        assert fila is not None
        assert fila[0] == 1
