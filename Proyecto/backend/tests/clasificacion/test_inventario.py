"""Pruebas del inventario sobre una biblioteca de ejemplo creada en una carpeta temporal."""

from pathlib import Path

import pytest

from tests.conftest import crear_pdf
from vetrag.clasificacion.inventario import (
    SIN_ESPECIALIDAD,
    construir_inventario,
    recorrer_archivos,
)
from vetrag.clasificacion.modelos import (
    Idioma,
    Recomendacion,
    RegistroArchivo,
    SenalRuido,
    TipoContenido,
)
from vetrag.clasificacion.reporte import escribir_csv, generar_resumen

PAGINA_ES = (
    "El parvovirus canino es una de las enfermedades más frecuentes en los cachorros que no "
    "han sido vacunados y se transmite por contacto con las heces de otros perros de la zona. "
    "Para el diagnóstico se usa una prueba rápida y el tratamiento es de soporte con fluidos."
)


@pytest.fixture
def biblioteca(tmp_path: Path) -> Path:
    raiz = tmp_path / "assets"
    base = raiz / "Mi biblioteca"
    (base / "Infecciosas").mkdir(parents=True)
    crear_pdf(base / "Infecciosas" / "Parvovirus.pdf", [PAGINA_ES] * 5)
    crear_pdf(base / "Infecciosas" / "Parvovirus(1).pdf", [PAGINA_ES] * 5)
    crear_pdf(base / "Escaneado.pdf", [""] * 5)
    crear_pdf(base / "certificado antibiotico.pdf", [PAGINA_ES] * 3)
    (base / "video.mov").write_bytes(b"\x00" * 10)
    (base / "curso.pptx").write_bytes(b"PK")
    (base / ".DS_Store").write_bytes(b"")
    (raiz / "README.md").write_text("no es parte del corpus")
    return raiz


@pytest.fixture
def inventario(biblioteca: Path) -> dict[str, RegistroArchivo]:
    registros = construir_inventario(biblioteca, trabajadores=1)
    return {r.ruta_relativa.name: r for r in registros}


def test_ignora_ocultos_y_readme(biblioteca: Path) -> None:
    nombres = {r.name for r in recorrer_archivos(biblioteca)}
    assert ".DS_Store" not in nombres
    assert "README.md" not in nombres
    assert len(nombres) == 6


def test_pdf_con_texto(inventario: dict[str, RegistroArchivo]) -> None:
    registro = inventario["Parvovirus.pdf"]
    assert registro.tipo_contenido is TipoContenido.TEXTO
    assert registro.idioma is Idioma.ESPANOL
    assert registro.especialidad == "Infecciosas"
    assert registro.paginas == 5
    assert registro.recomendacion is Recomendacion.CONSERVAR


def test_duplicado_apunta_al_original(inventario: dict[str, RegistroArchivo]) -> None:
    copia = inventario["Parvovirus(1).pdf"]
    assert SenalRuido.DUPLICADO in copia.senales
    assert copia.duplicado_de is not None
    assert copia.duplicado_de.name == "Parvovirus.pdf"
    assert copia.recomendacion is Recomendacion.DESCARTAR


def test_escaneado(inventario: dict[str, RegistroArchivo]) -> None:
    registro = inventario["Escaneado.pdf"]
    assert registro.tipo_contenido is TipoContenido.ESCANEADO
    assert registro.especialidad == SIN_ESPECIALIDAD
    assert registro.recomendacion is Recomendacion.CONSERVAR  # se recupera con OCR


def test_ruido_y_formatos(inventario: dict[str, RegistroArchivo]) -> None:
    assert inventario["certificado antibiotico.pdf"].recomendacion is Recomendacion.DESCARTAR
    assert inventario["video.mov"].recomendacion is Recomendacion.DESCARTAR
    assert inventario["curso.pptx"].tipo_contenido is TipoContenido.DOCUMENTO
    assert inventario["curso.pptx"].recomendacion is Recomendacion.CONSERVAR


def test_reportes(inventario: dict[str, RegistroArchivo], tmp_path: Path) -> None:
    registros = list(inventario.values())
    destino = tmp_path / "salida" / "inventario.csv"
    escribir_csv(registros, destino)
    contenido = destino.read_text(encoding="utf-8-sig")
    assert contenido.splitlines()[0].startswith("ruta_relativa,especialidad")
    assert len(contenido.splitlines()) == len(registros) + 1
    resumen = generar_resumen(registros)
    assert "## Archivos a descartar (3)" in resumen
