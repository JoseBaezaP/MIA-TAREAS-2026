# 04_limpio/ — Documentos en Markdown limpios (F2)

Salida del paso de limpieza (`uv run vetrag-ingesta limpiar`): los mismos `.md` de
`03_markdown/`, sin encabezados/pies de página repetidos, sin números de página sueltos,
sin datos personales y con las unidades `µg` corregidas. Se conservan las marcas
`<!-- pagina: N -->` y la cabecera de metadatos.

| Archivo | Contenido |
|---|---|
| `manifiesto.csv` | Cambios por documento (líneas repetidas, datos personales, unidades) |
| `reporte_limpieza.csv` | **Cada cambio**: documento, página, tipo, regla, texto original y reemplazo. Sirve para revisar que no se borró nada de más |

## ¿Por qué no se sube a GitHub?

Es el texto completo de los libros (derechos de autor), y el reporte contiene justamente los
datos personales que se eliminaron.
