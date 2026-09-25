# 01_clasificacion/ — Inventario del corpus (F1)

Salida de la fase de clasificación (`uv run vetrag-clasificar`).

| Archivo | Contenido |
|---|---|
| `inventario.csv` | Una fila por archivo de `assets/`: tipo de contenido (texto / escaneado / mixto), páginas, idioma, calidad del texto, duplicados, señales de ruido, recomendación y una muestra del texto |
| `resumen.md` | Totales por tipo, idioma, recomendación y especialidad |

La columna **`decision`** del CSV viene prellenada con la recomendación automática y **se
revisa a mano**: es la que usa la F2 para decidir qué archivos procesa.

## ¿Por qué no se sube a GitHub?

El inventario incluye muestras del texto de los libros y los nombres de todos los archivos
de la biblioteca personal. El proceso que lo genera sí está publicado en
[`backend/src/vetrag/clasificacion`](../../backend/src/vetrag/clasificacion).
