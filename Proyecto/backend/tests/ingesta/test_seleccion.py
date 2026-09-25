"""Pruebas de la selección de documentos a partir del inventario."""

import csv
import unicodedata
from pathlib import Path

import pytest

from vetrag.clasificacion.modelos import TipoContenido
from vetrag.ingesta.seleccion import (
    filtrar_piloto,
    leer_lista_piloto,
    leer_seleccion,
    normalizar_ruta,
)

COLUMNAS = ("ruta_relativa", "especialidad", "tipo_contenido", "idioma", "calidad_texto",
            "paginas", "decision")  # fmt: skip


@pytest.fixture
def inventario(tmp_path: Path) -> Path:
    ruta = tmp_path / "inventario.csv"
    filas = [
        # Ruta en NFD, como la guarda macOS.
        (unicodedata.normalize("NFD", "Bib/Virología/Capítulo 5.pdf"), "Virología",
         "escaneado", "desconocido", "", "45", "conservar"),
        ("Bib/Endocrino/libro.pdf", "Endocrino", "texto", "es", "0.91", "50", " Conservar "),
        ("Bib/certificado.pdf", "(sin carpeta)", "texto", "es", "0.9", "1", "descartar"),
        ("Bib/Fisio/Sangre.pptx", "Fisio", "documento", "desconocido", "", "", "conservar"),
    ]  # fmt: skip
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        escritor.writerows(filas)
    return ruta


def test_normalizar_ruta_unifica_acentos() -> None:
    nfd = unicodedata.normalize("NFD", "Virología")
    assert nfd != "Virología"  # se ven igual, pero son distintos
    assert normalizar_ruta(nfd) == "Virología"


def test_leer_seleccion_solo_conservar(inventario: Path) -> None:
    documentos = leer_seleccion(inventario)
    nombres = [d.ruta_relativa.name for d in documentos]
    assert nombres == ["Capítulo 5.pdf", "libro.pdf", "Sangre.pptx"]


def test_leer_seleccion_convierte_tipos(inventario: Path) -> None:
    escaneado, texto, pptx = leer_seleccion(inventario)
    assert escaneado.tipo_contenido is TipoContenido.ESCANEADO
    assert escaneado.calidad_texto is None
    assert texto.calidad_texto == pytest.approx(0.91)
    assert texto.paginas == 50
    assert pptx.paginas is None


def test_filtrar_piloto_con_acentos(inventario: Path, tmp_path: Path) -> None:
    lista = tmp_path / "piloto.txt"
    lista.write_text("# comentario\nBib/Virología/Capítulo 5.pdf\n\n", encoding="utf-8")
    elegidos = filtrar_piloto(leer_seleccion(inventario), leer_lista_piloto(lista))
    assert [d.ruta_relativa.name for d in elegidos] == ["Capítulo 5.pdf"]


def test_filtrar_piloto_avisa_si_falta_un_documento(inventario: Path) -> None:
    with pytest.raises(ValueError, match="certificado"):
        filtrar_piloto(leer_seleccion(inventario), {"Bib/certificado.pdf"})
