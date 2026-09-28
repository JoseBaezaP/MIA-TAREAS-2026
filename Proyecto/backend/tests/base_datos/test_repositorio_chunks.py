"""Pruebas del repositorio contra PostgreSQL real.

Solo corren si existe ``VETRAG_TEST_DATABASE_URL`` (una base de pruebas, NUNCA la del
proyecto): crean las tablas en un esquema temporal y lo borran al terminar.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest

from tests.ingesta.test_vectorizacion import chunk
from vetrag.base_datos.conexion import crear_esquema
from vetrag.base_datos.repositorio_chunks import RepositorioChunks, vector_a_texto

URL = os.environ.get("VETRAG_TEST_DATABASE_URL")


def test_vector_a_texto() -> None:
    assert vector_a_texto([0.1, -2.0, 3.5]) == "[0.1,-2,3.5]"


@pytest.fixture
def conexion() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    if URL is None:
        pytest.skip("sin VETRAG_TEST_DATABASE_URL")
    with psycopg.connect(URL) as con:
        con.execute(
            "CREATE SCHEMA IF NOT EXISTS prueba_vetrag; SET search_path TO prueba_vetrag, public"
        )
        crear_esquema(con)
        yield con
        con.execute("DROP SCHEMA prueba_vetrag CASCADE")
        con.commit()


def test_guardar_y_contar(conexion: psycopg.Connection[tuple[object, ...]]) -> None:
    repositorio = RepositorioChunks(conexion)
    repositorio.guardar([chunk(1), chunk(2)], [[0.1] * 1024, [0.2] * 1024], 1000, "voyage-4")
    assert repositorio.contar() == 2
    assert repositorio.ids_existentes() == {"id1", "id2"}
    assert repositorio.tokens_usados("voyage-4") == 1000
