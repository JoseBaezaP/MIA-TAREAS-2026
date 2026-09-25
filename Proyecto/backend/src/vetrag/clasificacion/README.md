# clasificacion/ — F1: Clasificación del corpus

Recorre `assets/` y genera un inventario para decidir **qué documentos entran al RAG** antes
de gastar tiempo de OCR o tokens de embeddings.

## Qué detecta en cada archivo

| Señal | Cómo se detecta |
|---|---|
| **Tipo de contenido** | Extrae el texto de ~12 páginas repartidas por el documento (con `pypdfium2`). Menos de 200 caracteres por página → `escaneado`; algunas páginas sí y otras no → `mixto`; el resto → `texto` |
| **Idioma** | Cuenta palabras muy frecuentes y exclusivas de cada idioma (*de, la, que…* vs *the, of, and…*) en la muestra de texto |
| **Calidad del texto** | Proporción de palabras "reales" en la muestra; un valor bajo indica OCR antiguo de mala calidad |
| **Duplicados** | Mismo contenido binario (hash SHA-256), aunque el nombre sea distinto |
| **Ruido por nombre** | Palabras como *certificado, convocatoria, calendario, peluquería…* en el nombre del archivo |
| **Nombre no descriptivo** | Nombres tipo hash o solo números (`6530481.pdf`): se marcan para revisarlos a mano |
| **Formato no soportado** | Video, calendario, etc. Los `.zip` se marcan para revisar (pueden contener PDFs) |

Con esas señales asigna una **recomendación**: `conservar`, `revisar` o `descartar`.
**No borra nada**: la decisión final se toma a mano en la columna `decision` del CSV.

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `modelos.py` | Tipos de datos: `RegistroArchivo`, `TipoContenido`, `Recomendacion` |
| `lector_pdf.py` | Lee páginas y texto de un PDF (aislado del resto para poder cambiar de librería) |
| `detectores.py` | Funciones puras que detectan cada señal (se prueban sin PDFs reales) |
| `inventario.py` | Recorre `assets/`, aplica los detectores, busca duplicados y recomienda |
| `reporte.py` | Escribe `inventario.csv` y `resumen.md` en `data/01_clasificacion/` |
| `__main__.py` | Punto de entrada de la línea de comandos |

## Uso

```bash
cd backend
uv run vetrag-clasificar
```

Salida: [`data/01_clasificacion/`](../../../../data/01_clasificacion).
