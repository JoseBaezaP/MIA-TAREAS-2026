# data/ — Resultados de cada fase del pipeline

Cada subcarpeta guarda la salida de un paso del pipeline, numerada en el orden en que se
ejecuta:

| Carpeta | Fase | Contenido |
|---|---|---|
| [`01_clasificacion/`](01_clasificacion) | F1 | Inventario del corpus y decisión por archivo |
| [`02_ocr/`](02_ocr) | F2 | PDFs con capa de texto (OCR) |
| [`03_markdown/`](03_markdown) | F2 | Documentos convertidos a Markdown (sin limpiar) |
| [`04_limpio/`](04_limpio) | F2 | Markdown limpio: sin encabezados repetidos ni datos personales |
| [`05_chunks/`](05_chunks) | F2 | Fragmentos (chunks) con metadatos, listos para vectorizar |

## ¿Por qué no se sube a GitHub?

Todo lo que hay aquí **se deriva del texto de los libros** de [`assets/`](../assets), así que
tiene los mismos problemas de derechos de autor y tamaño. En el repositorio solo quedan
estos README; el contenido se regenera ejecutando cada fase (ver
[`backend/README.md`](../backend/README.md)).
