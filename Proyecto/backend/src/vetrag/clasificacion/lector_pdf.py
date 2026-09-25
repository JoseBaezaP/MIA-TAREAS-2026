"""Lectura de PDFs.

Aislada del resto del módulo para que cambiar de librería (hoy ``pypdfium2``) solo afecte
a este archivo.
"""

from pathlib import Path

import pypdfium2 as pdfium

from vetrag.clasificacion.modelos import MuestraPdf

PAGINAS_A_MUESTREAR = 12


def indices_muestra(total_paginas: int, cantidad: int = PAGINAS_A_MUESTREAR) -> list[int]:
    """Índices de ``cantidad`` páginas repartidas uniformemente por el documento.

    Se muestrea todo el documento, no solo el inicio, para detectar libros que mezclan
    páginas digitales y escaneadas.
    """
    if total_paginas <= 0:
        return []
    if total_paginas <= cantidad:
        return list(range(total_paginas))
    paso = (total_paginas - 1) / (cantidad - 1)
    return sorted({round(i * paso) for i in range(cantidad)})


def leer_muestra(ruta: Path, cantidad: int = PAGINAS_A_MUESTREAR) -> MuestraPdf:
    """Cuenta las páginas del PDF y extrae el texto de una muestra de ellas.

    Raises:
        pypdfium2.PdfiumError: si el PDF está dañado o protegido con contraseña.
    """
    documento = pdfium.PdfDocument(ruta)
    try:
        total = len(documento)
        textos: list[str] = []
        for indice in indices_muestra(total, cantidad):
            pagina = documento[indice]
            capa_texto = pagina.get_textpage()
            textos.append(capa_texto.get_text_range())
            capa_texto.close()
            pagina.close()
    finally:
        documento.close()
    return MuestraPdf(paginas=total, textos=tuple(textos))
