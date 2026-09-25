"""Pruebas del paso de conversión a Markdown."""

from pathlib import Path

import anydoc
import pytest

from tests.conftest import crear_pdf
from vetrag.clasificacion.modelos import TipoContenido
from vetrag.ingesta.conversion import (
    PATRON_MARCA_PAGINA,
    EstadoConversion,
    construir_front_matter,
    convertir_documento,
    convertir_paginas,
    ejecutar_conversion,
    ruta_markdown,
    separar_paginas,
    unir_paginas,
)
from vetrag.ingesta.seleccion import DocumentoSeleccionado


def documento(
    nombre: str = "libro.pdf", tipo: TipoContenido = TipoContenido.TEXTO
) -> DocumentoSeleccionado:
    return DocumentoSeleccionado(
        ruta_relativa=Path("Bib") / "Virología" / nombre,
        especialidad="Virología",
        tipo_contenido=tipo,
        idioma="es",
        calidad_texto=0.9,
        paginas=3,
    )


def test_unir_paginas_marca_cada_pagina() -> None:
    markdown = unir_paginas(["# Parvovirus", "", "Distemper"])
    assert PATRON_MARCA_PAGINA.findall(markdown) == ["1", "2", "3"]
    assert markdown.index("# Parvovirus") < markdown.index("<!-- pagina: 2 -->")


def test_front_matter_escapa_caracteres_especiales() -> None:
    cabecera = construir_front_matter({"documento": 'Capítulo 5: "Diagnóstico"', "paginas": 45})
    assert cabecera.startswith("---\n")
    assert 'documento: "Capítulo 5: \\"Diagnóstico\\""' in cabecera
    assert "paginas: 45" in cabecera


def test_ruta_markdown_conserva_la_extension() -> None:
    assert ruta_markdown(Path("md"), Path("Bib/libro.pdf")) == Path("md/Bib/libro.pdf.md")


def test_separar_y_convertir_paginas(tmp_path: Path) -> None:
    pdf = crear_pdf(tmp_path / "libro.pdf", ["Parvovirus canino", "", "Distemper canino"])
    paginas = separar_paginas(pdf)
    assert len(paginas) == 3
    convertidas = convertir_paginas(paginas)
    assert "Parvovirus canino" in convertidas.textos[0]
    assert convertidas.textos[1] == ""
    assert "Distemper canino" in convertidas.textos[2]
    assert convertidas.vacias == 1


def test_convertir_documento_pdf(tmp_path: Path) -> None:
    fuente = crear_pdf(tmp_path / "libro.pdf", ["Parvovirus canino", "Distemper canino"])
    resultado = convertir_documento(documento(), fuente, tmp_path / "md")
    assert resultado.estado is EstadoConversion.CONVERTIDO
    assert resultado.ruta_markdown is not None
    contenido = resultado.ruta_markdown.read_text(encoding="utf-8")
    assert contenido.startswith('---\ndocumento: "libro"\nespecialidad: "Virología"')
    pagina_2 = contenido.split("<!-- pagina: 2 -->")[1]
    assert "Distemper canino" in pagina_2
    assert "Parvovirus canino" not in pagina_2
    assert resultado.paginas == 2


def test_convertir_documento_reanuda(tmp_path: Path) -> None:
    fuente = crear_pdf(tmp_path / "libro.pdf", ["Parvovirus canino"])
    convertir_documento(documento(), fuente, tmp_path / "md")
    segunda = convertir_documento(documento(), fuente, tmp_path / "md")
    assert segunda.estado is EstadoConversion.YA_EXISTIA


def test_convertir_documento_error_no_deja_archivos(tmp_path: Path) -> None:
    fuente = tmp_path / "libro.pdf"
    fuente.write_bytes(b"esto no es un pdf")
    resultado = convertir_documento(documento(), fuente, tmp_path / "md")
    assert resultado.estado is EstadoConversion.ERROR
    assert not (tmp_path / "md").exists()


def test_ejecutar_conversion_sin_manifiesto_ocr(tmp_path: Path) -> None:
    (resultado,) = ejecutar_conversion([documento()], fuentes={}, ruta_salida=tmp_path)
    assert resultado.estado is EstadoConversion.ERROR
    assert "ocr" in resultado.mensaje


def test_plan_b_texto_plano_si_anydoc_rechaza_la_pagina(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def rechazar(_datos: bytes, _formato: str) -> str:
        raise anydoc.UnsupportedError("PDF has no extractable text (ImageBased)")

    monkeypatch.setattr(anydoc, "to_markdown_bytes", rechazar)
    pdf = crear_pdf(tmp_path / "diapositivas.pdf", ["Diagnóstico de laboratorio", ""])
    convertidas = convertir_paginas(separar_paginas(pdf))
    assert "Diagnóstico de laboratorio" in convertidas.textos[0]
    assert convertidas.texto_plano == 1
    assert convertidas.vacias == 1
