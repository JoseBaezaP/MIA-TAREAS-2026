# 05_chunks/ — Fragmentos listos para vectorizar (F2)

| Archivo | Contenido |
|---|---|
| `chunks.jsonl` | Un chunk por línea (JSON) con su texto, el texto con encabezado de contexto para el embedding y sus metadatos (documento, especialidad, idioma, ruta de títulos, páginas, unidades dudosas) |
| `resumen.json` | Totales: chunks, tokens, duplicados descartados, chunks con unidades dudosas |

Es la entrada del paso de vectorización con Voyage AI.

## ¿Por qué no se sube a GitHub?

Cada chunk contiene texto literal de los libros (derechos de autor).
