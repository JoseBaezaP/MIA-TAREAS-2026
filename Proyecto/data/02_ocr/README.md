# 02_ocr/ — PDFs con capa de texto (F2)

Copias de los PDFs aprobados en la F1 procesadas con `ocrmypdf -l spa+eng`, con la misma ruta
de carpetas que en `assets/`. El modo de OCR de cada documento (`--skip-text`, `--redo-ocr` o
ninguno) se explica en el [README de la ingesta](../../backend/src/vetrag/ingesta/README.md).

| Archivo | Contenido |
|---|---|
| `manifiesto.csv` | Modo de OCR de cada documento y **qué archivo debe leer el paso siguiente** (el PDF con OCR o el original) |
| `ocr_completo.log` | Bitácora de la corrida completa |

Corpus completo: 111 documentos con OCR, 202 que no lo necesitaron y 9 con PDFs originales
dañados que se quedaron con su texto original (ver [`pendientes/`](../pendientes)). ~19 GB.

## ¿Por qué no se sube a GitHub?

Son copias de los libros originales (derechos de autor, ~19 GB).
