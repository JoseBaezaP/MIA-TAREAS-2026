# ingesta/ — F2: De PDF a vectores

Convierte los documentos aprobados en la F1 (`decision = conservar`) en vectores guardados
en pgvector:

```
PDF ─► ocr.py ─► conversion.py ─► limpieza.py ─► chunking.py ─► vectorizacion.py ─► pgvector
       (ocrmypdf) (anydoc → Markdown) (ruido)    (~800 tokens)   (Voyage voyage-4)
```

Cada paso escribe su salida en `data/0X_*/` (`02_ocr`, `03_markdown`, `04_limpio`, `05_chunks`), así que el proceso se puede retomar desde
cualquier paso sin repetir los anteriores.

| Paso | Estado |
|---|---|
| 1. OCR | ✅ Probado en el piloto (10 documentos) |
| 2. Conversión a Markdown | ✅ Probado en el piloto (10 documentos) |
| 3. Limpieza | ✅ Probado en el piloto (10 documentos) |
| 4. Chunking | ⏳ |
| 5. Vectorización | ⏳ |

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `seleccion.py` | Lee `inventario.csv` y devuelve los documentos con `decision = conservar`; filtra el piloto |
| `ocr.py` | Elige el modo de OCR de cada documento y ejecuta `ocrmypdf`; escribe el manifiesto |
| `conversion.py` | Convierte cada documento a Markdown con `anydoc`, página por página, con marcas de página |
| `limpieza.py` | Quita encabezados repetidos, números de página y datos personales; corrige µg; genera el reporte |
| `unidades.py` | Catálogo de unidades (prefijos SI × unidades base, anglosajonas y clínicas) para distinguir unidades reales de errores de OCR |
| `__main__.py` | Comando `vetrag-ingesta` con un subcomando por paso |

## Paso 1: OCR

El modo de OCR se elige con lo que la F1 ya sabe de cada documento:

| Inventario (F1) | Modo | `ocrmypdf` |
|---|---|---|
| PowerPoint / Word / EPUB | `no_aplica` | — (pasa directo al paso 2) |
| `texto` con buena calidad | `no_necesario` | — (se usa el original) |
| Calidad del texto < 0.7 | `rehacer` | `--redo-ocr`: reemplaza el OCR viejo |
| `escaneado` o `mixto` | `completar` | `--skip-text`: OCR solo en las páginas sin texto |

- El original nunca se modifica: la salida va a `data/02_ocr/`, con la misma ruta de carpetas.
- **Se puede reanudar**: si el PDF de salida ya existe, se salta. Se escribe primero en un
  `.tmp`, así una corrida interrumpida no deja un PDF a medias con el nombre final.
- `data/02_ocr/manifiesto.csv` indica, para cada documento, **qué archivo debe leer el paso
  siguiente** (el PDF con OCR o el original).

```bash
uv run vetrag-ingesta ocr --piloto   # solo los documentos de data/piloto.txt
uv run vetrag-ingesta ocr            # todos los documentos conservados
```

### Resultados del piloto

| Documento | Modo | Antes | Después |
|---|---|---|---|
| Libro escaneado (50 p.) | completar | 0 car/pág | 1,838 car/pág, calidad 0.86 |
| Atlas con OCR viejo (116 p.) | rehacer | calidad 0.63 | calidad **0.87** |
| Tabla de dosis escaneada (4 p.) | completar | 2 car/pág | 732 car/pág, calidad 0.67 |
| Presentación exportada a PDF (45 p.) | completar | 75 car/pág | 335 car/pág (las diapositivas son títulos + fotos) |

⚠️ **Hallazgo crítico:** el OCR confunde **µg** (microgramos) con `pg` (picogramos) o con
`yg`, `1g`, `g` en las tablas de dosis. Es un error de **un millón de veces** en una dosis.
Se corrige en el paso 3 (limpieza), y el agente siempre debe citar la fuente (ver
`docs/decisiones.md`, D8).

## Paso 2: conversión a Markdown

`anydoc` convierte un PDF completo en un solo bloque de Markdown, **sin indicar de qué página
viene cada texto**. Para poder citar la página, cada PDF se divide en PDFs de una página
(`pypdfium2`), cada uno se convierte por separado y se unen con una marca invisible:

```markdown
---
documento: "Manual de bacteriología 2020"
especialidad: "Bacteriología Vet"
idioma: "es"
fuente: "Mi biblioteca Veterinaria/Bacteriología Vet/Manual de bacteriología 2020.pdf"
paginas: 42
---

<!-- pagina: 1 -->
## UNIVERSIDAD AUTÓNOMA DE NUEVO LEÓN
...
<!-- pagina: 2 -->
```

- La cabecera (*front matter*) lleva los metadatos que usarán el chunking y las citas.
- **Plan B**: anydoc rechaza algunas páginas que sí tienen texto. En el piloto fueron
  páginas con muy poco texto (~70-100 caracteres) y alguna imagen, como una diapositiva con
  título y foto; una página escaneada al 100 % pero con ~1,000 caracteres de OCR sí la
  convirtió, así que no depende del tamaño de la imagen. Como su regla exacta es interna,
  **cada vez** que rechaza una página se usa el texto plano de `pypdfium2`. En el piloto, una
  presentación pasó de 30 páginas vacías a 3 (las 3 que de verdad no tienen texto).
- **Página vacía** = ni anydoc ni `pypdfium2` encontraron texto.
- Los PowerPoint/Word se convierten completos, sin marcas de página.
- Se puede reanudar (si el `.md` ya existe, se salta) y deja `data/03_markdown/manifiesto.csv`.

```bash
uv run vetrag-ingesta convertir --piloto
```

## Paso 3: limpieza

Lee `data/03_markdown/` y escribe en `data/04_limpio/`, sin modificar la conversión: si una
regla borra de más, se corrige y se vuelve a limpiar sin volver a convertir. Se rehace
completa en cada corrida (tarda segundos).

| Tarea | Regla | Protecciones ("trampas" probadas) |
|---|---|---|
| Encabezados y pies repetidos | Línea en ≥ 50 % de las páginas (los números de los extremos cuentan como `#`) | Nunca toca líneas de tabla (`\|`); solo en documentos de ≥ 5 páginas; los números internos sí distinguen líneas |
| Datos personales | `Nombre:`, `Matrícula:`, `Alumno:`, `Propietario:`, `Técnico de lab.:`; listas después de `Equipo:`/`Integrantes`; nombre + matrícula; teléfonos; correos | Sin regla de direcciones ("colonia" bacteriana); `Paciente:` se conserva (describe al animal); autores y epónimos (Cushing, Addison) se conservan |
| Unidades | `ug` → `µg` siempre; `pg`, `yg`, `1g` + `/kg` → `µg/kg` **solo en documentos con OCR y en líneas de dosis** (IV, IM, CRI, bolo…) | `pg/kg` real en un PDF digital no se toca (residuos en alimentos); `g/kg`, `mol/kg`, `mval/l`, `mg/lb` no se tocan; lo que no está en el catálogo de `unidades.py` (`1a/kg`, `ma/kg`) solo se **reporta** |
| Números de página | Líneas con solo `12`, `- 12 -`, `Página 12`, `12 de 40` | `Dosis 12 mg`, `1. Introducción` se conservan |

`data/04_limpio/reporte_limpieza.csv` registra **cada cambio** (documento, página, regla,
texto original y reemplazo) para revisarlo a mano.

```bash
uv run vetrag-ingesta limpiar --piloto
```

**Piloto:** 18 unidades corregidas a µg, 5 unidades fuera del catálogo reportadas, 7 datos personales eliminados (nombre y matrícula de
una estudiante, 4 integrantes de un equipo, un correo y un teléfono), 7 encabezados/pies
repetidos y 3 unidades sospechosas reportadas.
