"""Utilidades compartidas por las pruebas."""

from pathlib import Path


def crear_pdf(ruta: Path, paginas: list[str]) -> Path:
    """Crea un PDF mínimo válido: una página por elemento, con ese texto (vacío = sin texto).

    Se escribe a mano para no depender de otra librería solo para las pruebas.
    """
    objetos: list[bytes] = []
    n = len(paginas)
    ids_paginas = [4 + 2 * i for i in range(n)]
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{i} 0 R" for i in ids_paginas)
    objetos.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, texto in enumerate(paginas):
        lineas = [texto[j : j + 80] for j in range(0, len(texto), 80)]
        lineas_pdf = " ".join(
            f"({linea.replace('(', '').replace(')', '')}) Tj 0 -12 Td" for linea in lineas
        )
        comandos = f"BT /F1 10 Tf 40 800 Td {lineas_pdf} ET"
        contenido = comandos.encode("latin-1")
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {ids_paginas[i] + 1} 0 R >>".encode()
        )
        objetos.append(
            f"<< /Length {len(contenido)} >>\nstream\n".encode() + contenido + b"\nendstream"
        )

    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += b"".join(f"{p:010d} 00000 n \n".encode() for p in posiciones)
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    ruta.write_bytes(bytes(salida))
    return ruta
