# pendientes/ — Documentos para reprocesar al final

Documentos que fallaron en algún paso de la F2 y se dejaron para **reprocesarlos cuando el
flujo completo esté terminado**, para no bloquear el avance del resto del corpus.

| Archivo | Contenido |
|---|---|
| `pendientes.csv` | Una fila por documento: paso donde falló, problema detectado y solución propuesta |

## Problemas registrados (2026-09-27)

| Paso | Problema | Documentos | Solución propuesta |
|---|---|---|---|
| 1. OCR | `--skip-text` se saltó las páginas porque tienen una capa de texto "fantasma" (existe en el PDF pero no se puede extraer) | 8 | Repetir con `--force-ocr` y verificar que el resultado tenga texto |
| 1. OCR | El PDF de salida del OCR no se puede abrir | 1 | Repetir con `--force-ocr` desde el original |
| 2. Conversión | `pypdfium2` no puede separar una página | 1 | Saltar la página dañada |
| 2. Conversión | EPUB ilegible / HTML no soportado por anydoc | 2 | Probar con `markitdown` |

Mientras tanto, esos documentos no generan chunks (o solo de las pocas páginas que sí tienen
texto), así que no afectan al resto del pipeline.

## Mejoras pendientes del pipeline

| Paso | Mejora | Motivo |
|---|---|---|
| 3. Limpieza | Unir palabras cortadas con guion al final de línea (`pro- liferations` → `proliferations`), solo entre letras | Mejora un poco la búsqueda |
| 4. Chunking | Usar el idioma del documento completo cuando un chunk corto sale como "desconocido" (2,896 chunks) | Mejor metadato de idioma |
| 4. Chunking | Si la **última** sección de un bloque tiene < 20 tokens (p. ej. una oración corta), unirla al chunk anterior en lugar de descartarla | Hoy se pierde (se descarta como si fuera basura) |

## ¿Por qué no se sube a GitHub?

`pendientes.csv` contiene los nombres de los libros de la biblioteca personal.
