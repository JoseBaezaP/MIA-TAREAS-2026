"""Pruebas del paso de OCR."""

import shutil
from pathlib import Path

import pytest

from tests.conftest import crear_pdf
from vetrag.clasificacion.modelos import TipoContenido
from vetrag.ingesta.ocr import (
    EstadoOcr,
    ModoOcr,
    construir_comando,
    elegir_modo_ocr,
    escribir_manifiesto,
    procesar_documento,
)
from vetrag.ingesta.seleccion import DocumentoSeleccionado

requiere_ocrmypdf = pytest.mark.skipif(
    shutil.which("ocrmypdf") is None, reason="ocrmypdf no está instalado"
)


def documento(
    tipo: TipoContenido, calidad: float | None = None, nombre: str = "libro.pdf"
) -> DocumentoSeleccionado:
    return DocumentoSeleccionado(
        ruta_relativa=Path("Bib") / nombre,
        especialidad="Bib",
        tipo_contenido=tipo,
        idioma="es",
        calidad_texto=calidad,
        paginas=3,
    )


@pytest.mark.parametrize(
    ("tipo", "calidad", "esperado"),
    [
        (TipoContenido.TEXTO, 0.92, ModoOcr.NO_NECESARIO),
        (TipoContenido.ESCANEADO, None, ModoOcr.COMPLETAR),
        (TipoContenido.MIXTO, 0.88, ModoOcr.COMPLETAR),
        (TipoContenido.MIXTO, 0.63, ModoOcr.REHACER),  # OCR viejo de mala calidad
        (TipoContenido.TEXTO, 0.51, ModoOcr.REHACER),
        (TipoContenido.DOCUMENTO, None, ModoOcr.NO_APLICA),
    ],
)
def test_elegir_modo_ocr(tipo: TipoContenido, calidad: float | None, esperado: ModoOcr) -> None:
    assert elegir_modo_ocr(documento(tipo, calidad)) is esperado


def test_construir_comando_completar() -> None:
    comando = construir_comando(ModoOcr.COMPLETAR, Path("a.pdf"), Path("b.pdf"), trabajadores=4)
    assert comando[0] == "ocrmypdf"
    assert "--skip-text" in comando
    assert comando[comando.index("--language") + 1] == "spa+eng"
    assert comando[-2:] == ["a.pdf", "b.pdf"]


def test_construir_comando_rehacer() -> None:
    comando = construir_comando(ModoOcr.REHACER, Path("a.pdf"), Path("b.pdf"), trabajadores=4)
    assert "--redo-ocr" in comando
    assert "--skip-text" not in comando


def test_construir_comando_rechaza_modo_sin_ocr() -> None:
    with pytest.raises(ValueError):
        construir_comando(ModoOcr.NO_NECESARIO, Path("a.pdf"), Path("b.pdf"), trabajadores=1)


def test_sin_ocr_usa_el_original(tmp_path: Path) -> None:
    resultado = procesar_documento(
        documento(TipoContenido.TEXTO, 0.95), tmp_path / "assets", tmp_path / "ocr", 1
    )
    assert resultado.estado is EstadoOcr.OMITIDO
    assert resultado.ruta_fuente == tmp_path / "assets" / "Bib" / "libro.pdf"


def test_reanuda_si_ya_existe(tmp_path: Path) -> None:
    ya_hecho = tmp_path / "ocr" / "Bib" / "libro.pdf"
    ya_hecho.parent.mkdir(parents=True)
    ya_hecho.write_bytes(b"%PDF")
    resultado = procesar_documento(
        documento(TipoContenido.ESCANEADO), tmp_path / "assets", tmp_path / "ocr", 1
    )
    assert resultado.estado is EstadoOcr.YA_EXISTIA
    assert resultado.ruta_fuente == ya_hecho


@requiere_ocrmypdf
def test_ocr_real_en_pdf_mixto(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    (assets / "Bib").mkdir(parents=True)
    crear_pdf(assets / "Bib" / "libro.pdf", ["Parvovirus canino " * 20, ""])
    resultado = procesar_documento(documento(TipoContenido.MIXTO, 0.9), assets, tmp_path / "ocr", 1)
    assert resultado.estado is EstadoOcr.PROCESADO, resultado.mensaje
    assert resultado.ruta_fuente.exists()
    assert not list((tmp_path / "ocr").rglob("*.tmp"))  # no quedan temporales


@requiere_ocrmypdf
def test_ocr_real_error_no_deja_archivos(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    (assets / "Bib").mkdir(parents=True)
    (assets / "Bib" / "libro.pdf").write_bytes(b"esto no es un pdf")
    resultado = procesar_documento(documento(TipoContenido.ESCANEADO), assets, tmp_path / "ocr", 1)
    assert resultado.estado is EstadoOcr.ERROR
    assert resultado.ruta_fuente == assets / "Bib" / "libro.pdf"
    assert not list((tmp_path / "ocr").rglob("*.pdf*"))


def test_escribir_manifiesto(tmp_path: Path) -> None:
    resultado = procesar_documento(
        documento(TipoContenido.DOCUMENTO, nombre="Sangre.pptx"), tmp_path, tmp_path / "ocr", 1
    )
    destino = tmp_path / "ocr" / "manifiesto.csv"
    escribir_manifiesto([resultado], destino)
    lineas = destino.read_text(encoding="utf-8-sig").splitlines()
    assert lineas[0].startswith("ruta_relativa,modo,estado,ruta_fuente")
    assert "no_aplica,omitido" in lineas[1]
