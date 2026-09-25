"""Pruebas de la lectura de PDFs."""

from pathlib import Path

import pytest

from tests.conftest import crear_pdf
from vetrag.clasificacion.lector_pdf import indices_muestra, leer_muestra


@pytest.mark.parametrize(
    ("total", "cantidad", "esperado"),
    [
        (0, 12, []),
        (3, 12, [0, 1, 2]),
        (100, 5, [0, 25, 50, 74, 99]),
    ],
)
def test_indices_muestra(total: int, cantidad: int, esperado: list[int]) -> None:
    assert indices_muestra(total, cantidad) == esperado


def test_indices_muestra_incluye_primera_y_ultima_pagina() -> None:
    indices = indices_muestra(500)
    assert indices[0] == 0
    assert indices[-1] == 499
    assert len(indices) == 12


def test_leer_muestra_extrae_texto(tmp_path: Path) -> None:
    ruta = crear_pdf(tmp_path / "libro.pdf", ["Parvovirus canino", "", "Distemper"])
    muestra = leer_muestra(ruta)
    assert muestra.paginas == 3
    assert "Parvovirus canino" in muestra.textos[0]
    assert muestra.textos[1].strip() == ""


def test_leer_muestra_pdf_danado(tmp_path: Path) -> None:
    ruta = tmp_path / "danado.pdf"
    ruta.write_bytes(b"esto no es un pdf")
    with pytest.raises(Exception):  # noqa: B017 - pypdfium2 no expone una jerarquía estable
        leer_muestra(ruta)
