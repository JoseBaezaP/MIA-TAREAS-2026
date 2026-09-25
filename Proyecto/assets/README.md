# assets/ — Biblioteca veterinaria original

Contiene la biblioteca de origen del agente: ~360 archivos (324 PDFs, además de
presentaciones y otros formatos), unos **80,000 páginas** y **~14 GB**, organizados
en subcarpetas por especialidad (Dermatología, Farmacología, Cirugía, etc.).

## ¿Por qué no se sube a GitHub?

- **Derechos de autor**: la mayoría son libros y artículos publicados; redistribuirlos en un
  repositorio público no está permitido.
- **Tamaño**: ~14 GB superan por mucho los límites prácticos de GitHub.

## Reglas

- Esta carpeta es **de solo lectura** para el pipeline: ninguna fase modifica ni borra los
  archivos originales. Todo lo derivado se escribe en [`../data/`](../data).
- Qué archivos se usan y cuáles se descartan como ruido lo decide la
  [F1 Clasificación](../backend/src/vetrag/clasificacion).
