"""Escritura del inventario (CSV) y de su resumen (Markdown)."""

import csv
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

from vetrag.clasificacion.modelos import Recomendacion, RegistroArchivo

COLUMNAS = (
    "ruta_relativa",
    "especialidad",
    "extension",
    "tamano_mb",
    "paginas",
    "tipo_contenido",
    "caracteres_por_pagina",
    "proporcion_paginas_con_texto",
    "idioma",
    "calidad_texto",
    "duplicado_de",
    "senales",
    "recomendacion",
    "decision",
    "muestra_texto",
    "error",
    "sha256",
)


def _a_fila(registro: RegistroArchivo) -> dict[str, str]:
    def texto(valor: object) -> str:
        return "" if valor is None else str(valor)

    return {
        "ruta_relativa": str(registro.ruta_relativa),
        "especialidad": registro.especialidad,
        "extension": registro.extension,
        "tamano_mb": f"{registro.tamano_bytes / 1_048_576:.1f}",
        "paginas": texto(registro.paginas),
        "tipo_contenido": registro.tipo_contenido,
        "caracteres_por_pagina": texto(registro.caracteres_por_pagina),
        "proporcion_paginas_con_texto": texto(registro.proporcion_paginas_con_texto),
        "idioma": registro.idioma,
        "calidad_texto": texto(registro.calidad_texto),
        "duplicado_de": texto(registro.duplicado_de),
        "senales": "|".join(registro.senales),
        "recomendacion": registro.recomendacion,
        # Se prellena con la recomendación; se corrige a mano y la F2 solo usa esta columna.
        "decision": registro.recomendacion,
        "muestra_texto": registro.muestra_texto,
        "error": texto(registro.error),
        "sha256": registro.sha256,
    }


def escribir_csv(registros: Sequence[RegistroArchivo], destino: Path) -> None:
    """Escribe el inventario. Usa UTF-8 con BOM para que Excel respete los acentos."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(_a_fila(r) for r in registros)


def _tabla(encabezados: Sequence[str], filas: Sequence[Sequence[object]]) -> list[str]:
    lineas = [
        "| " + " | ".join(encabezados) + " |",
        "|" + "---|" * len(encabezados),
    ]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return lineas


def _conteo(registros: Sequence[RegistroArchivo], campo: str) -> list[tuple[str, int, int]]:
    archivos: Counter[str] = Counter()
    paginas: Counter[str] = Counter()
    for registro in registros:
        clave = str(getattr(registro, campo))
        archivos[clave] += 1
        paginas[clave] += registro.paginas or 0
    return [(clave, n, paginas[clave]) for clave, n in archivos.most_common()]


def generar_resumen(registros: Sequence[RegistroArchivo]) -> str:
    """Resumen en Markdown: totales por tipo, idioma, recomendación y especialidad."""
    total_paginas = sum(r.paginas or 0 for r in registros)
    total_gb = sum(r.tamano_bytes for r in registros) / 1_073_741_824
    lineas = [
        "# Resumen de la clasificación del corpus",
        "",
        f"- **Archivos analizados:** {len(registros)}",
        f"- **Páginas (PDF):** {total_paginas:,}",
        f"- **Tamaño total:** {total_gb:.1f} GB",
        "",
    ]
    for titulo, campo in (
        ("Por recomendación", "recomendacion"),
        ("Por tipo de contenido", "tipo_contenido"),
        ("Por idioma", "idioma"),
    ):
        lineas += [
            f"## {titulo}",
            "",
            *_tabla(("Valor", "Archivos", "Páginas"), _conteo(registros, campo)),
            "",
        ]

    por_especialidad: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for registro in registros:
        por_especialidad[registro.especialidad][registro.recomendacion] += 1
        por_especialidad[registro.especialidad]["paginas"] += registro.paginas or 0
    filas = [
        (
            especialidad,
            sum(c[r] for r in Recomendacion),
            c["paginas"],
            c[Recomendacion.CONSERVAR],
            c[Recomendacion.REVISAR],
            c[Recomendacion.DESCARTAR],
        )
        for especialidad, c in sorted(por_especialidad.items())
    ]
    lineas += [
        "## Por especialidad",
        "",
        *_tabla(
            ("Especialidad", "Archivos", "Páginas", "Conservar", "Revisar", "Descartar"), filas
        ),
        "",
    ]

    for recomendacion in (Recomendacion.DESCARTAR, Recomendacion.REVISAR):
        seleccion = [r for r in registros if r.recomendacion is recomendacion]
        lineas += [f"## Archivos a {recomendacion} ({len(seleccion)})", ""]
        lineas += _tabla(
            ("Archivo", "Señales", "Tipo", "Páginas"),
            [
                (
                    f"`{r.ruta_relativa}`",
                    ", ".join(r.senales),
                    r.tipo_contenido,
                    r.paginas if r.paginas is not None else "",
                )
                for r in seleccion
            ],
        )
        lineas.append("")
    return "\n".join(lineas)


def escribir_resumen(registros: Sequence[RegistroArchivo], destino: Path) -> None:
    """Escribe el resumen en Markdown."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar_resumen(registros), encoding="utf-8")
