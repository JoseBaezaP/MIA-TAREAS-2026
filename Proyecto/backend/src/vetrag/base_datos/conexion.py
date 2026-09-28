"""Conexión a PostgreSQL y creación del esquema."""

from pathlib import Path

import psycopg

RUTA_ESQUEMA = Path(__file__).with_name("esquema.sql")


def conectar(url: str) -> psycopg.Connection[tuple[object, ...]]:
    """Abre una conexión. ``url``: ``postgresql://usuario:contraseña@host:puerto/base``."""
    return psycopg.connect(url)


def crear_esquema(conexion: psycopg.Connection[tuple[object, ...]]) -> None:
    """Crea la extensión, las tablas y los índices si no existen (se puede repetir)."""
    conexion.execute(RUTA_ESQUEMA.read_text(encoding="utf-8").encode())
    conexion.commit()
