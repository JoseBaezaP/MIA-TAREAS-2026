# Registro de decisiones técnicas

Cada decisión con las alternativas que se evaluaron y su justificación.

## D1. Framework del agente: LangGraph

- **Alternativas**: Flowise, n8n, Agno, código nativo, LangGraph.
- **Descartadas**:
  - Flowise: el repositorio se archivó en agosto de 2026 (sin mantenimiento).
  - n8n: está orientado a automatización general más que a RAG.
  - Código nativo: habría que reimplementar el ciclo del agente y el uso de herramientas.
  - Agno: se evaluó y era la primera opción por ser simple, pero lo aprendido no se
    transfiere a LangGraph.js.
- **Elegida**: LangGraph. El flujo del agente queda explícito como grafo (estado, nodos,
  condiciones), lo que facilita explicarlo y evaluarlo. Además, los mismos conceptos se
  usan en LangGraph.js para otros proyectos en Node.js.

## D2. Embeddings: Voyage AI `voyage-4`

- **Alternativas**: OpenAI `text-embedding-3-small`, `bge-m3` local (Ollama),
  Voyage `voyage-3.5` / `voyage-4` / `voyage-4-lite`.
- **Elegida**: `voyage-4` (1024 dimensiones, 32K tokens de contexto, multilingüe). El
  corpus (~35–50 M tokens estimados) cabe en los 200 M tokens gratuitos de la familia
  voyage-4. `voyage-3.5` quedó como modelo de la generación anterior.
- **Restricción**: se usa el **endpoint síncrono**, no el Batch API, porque los tokens
  gratuitos no aplican al Batch API. El script lleva un contador de tokens con un límite
  de seguridad.
- **Consecuencia**: las preguntas del usuario deben vectorizarse con el mismo modelo, así
  que el servidor también llama a Voyage.

## D3. Base vectorial: PostgreSQL + pgvector

- SQL estándar, un solo motor para chunks y usuarios, índice HNSW. Con 1024 dimensiones
  queda dentro del límite de 2000 dimensiones del tipo `vector`.
- **Desarrollo**: se usa el PostgreSQL 14 que ya estaba instalado en la Mac (en lugar de
  Docker), con una base y un usuario propios (`vetrag`) para no tocar otros proyectos.
  pgvector 0.8.6 se compiló desde el código fuente (Homebrew solo lo trae para PG 17/18).
- **Producción**: la base se copia al EC2 (`pg_dump` / `pg_restore`); un respaldo de PG 14
  se restaura sin problema en una versión más nueva.

## D4. OCR: `ocrmypdf` con `--skip-text`

- 81 de 324 PDFs (~21,700 páginas) son escaneos sin texto extraíble.
- `ocrmypdf` (Tesseract, `spa+eng`) es gratuito y local. Con `--skip-text` solo procesa
  las páginas que no tienen texto.

## D5. Conversión a Markdown antes de dividir en chunks

- El texto plano pierde los títulos y desarma las tablas (por ejemplo, las de dosis).
- En Markdown se puede dividir por secciones y guardar en cada chunk la ruta de títulos
  (capítulo > sección). Herramienta principal: `anydoc`; alternativa: `markitdown`.
- Se valida en un piloto comparando texto plano contra Markdown.

## D6. Chunking determinista (sin LLM)

- Dividir con un LLM sobre ~40 M tokens tendría un costo alto y aportaría poco.
- Se divide por títulos de Markdown, con ~800 tokens por chunk y ~100 de traslape.

## D7. Qué se publica en GitHub

- El repositorio es público: se publica **el proceso** (clasificación, RAG y agente) y
  **no los datos**.
- Se excluyen los PDFs, los resultados intermedios, los volcados de la base, el módulo de
  autenticación y los secretos. Cada carpeta excluida tiene un README que explica por qué.

## D8. OCR por modos según el inventario, y el riesgo de las unidades

- El modo de OCR se elige con la F1: sin OCR si el texto ya es bueno, `--skip-text` para
  escaneados/mixtos y `--redo-ocr` si la calidad es < 0.7. En el piloto: 5 de 10 documentos
  no necesitaron OCR (ahorro de tiempo); el atlas con OCR viejo pasó de 0.63 a 0.87.
- Se probó `--redo-ocr` en una presentación exportada a PDF: no recuperó más texto útil
  (las diapositivas son títulos + fotos) y agregó basura al "leer" las fotos, así que se
  mantiene `--skip-text` para los mixtos.
- **Riesgo encontrado**: en la tabla de dosis, el OCR leyó `µg/kg` como `pg/kg`, `yg/kg`,
  `1g/kg`, `g/kg`. En medicina, confundir microgramos con picogramos o gramos es un error
  grave de dosificación. Mitigación:
  1. En la limpieza (paso 3), convertir `pg`, `yg`, `ug`, `1g` a `µg` cuando van junto a
     `/kg`, `/kg/h` o `/kg/min` (en dosis veterinarias no se usan picogramos). `g/kg` **no**
     se corrige automáticamente, porque también es una unidad real (p. ej., glucosa
     0.5 g/kg).
  2. El agente cita siempre la fuente (libro y página) para que la dosis se pueda verificar.

## D9. Limpieza determinista y datos personales

- La limpieza escribe en una carpeta aparte (`04_limpio/`) para poder ajustar las reglas y
  repetirla sin volver a convertir.
- **Datos personales**: se eliminan nombres **solo junto a etiquetas** (`Nombre:`,
  `Matrícula:`, `Equipo:`…), matrículas, teléfonos y correos. No se usa detección automática
  de nombres (NER) porque borraría epónimos médicos (síndrome de Cushing, tinción de Gram) y
  los autores de las fuentes.
- **Sin regla de direcciones** (decisión del autor): patrones como "Col." chocan con textos
  de bacteriología ("colonia") y en la literatura casi no hay direcciones personales.
- `Paciente:` no se trata como dato personal: en veterinaria describe al animal.
- Las pruebas detectaron un error antes del piloto: normalizar **todos** los números hacía que
  líneas de contenido distintas (`La catalasa 3…` / `La catalasa 4…`) parecieran encabezados
  repetidos. Solo se normalizan los números de los extremos de la línea.

## D10. Catálogo de unidades y corrección de µg según el origen del texto

- Se armó un catálogo combinando los **prefijos SI** (mega a pico) con las **unidades base**
  (g, mol, M, val, Eq, Osm, l, Pa, J, cal, kat, Bq, Gy, U, UI…), más unidades sin prefijo,
  anglosajonas (gr, oz, lb, pt, gal…) y clínicas (gotas, UFC). Fuente: tablas de unidades SI,
  prefijos y equivalencias anglosajonas de un libro de referencia del autor.
- **Cambio de regla a partir de esas tablas**: `pg/kg` es una unidad real (Tabla 2: pico,
  10⁻¹²; residuos en alimentos). Por eso `pg`/`yg`/`1g` → `µg` solo se corrige cuando el
  documento pasó por OCR **y** la línea tiene contexto de dosis. En un PDF digital el texto
  es exacto. `ug` sí se corrige siempre (no es una unidad; es `µg` sin el símbolo).
- **Se respetan mayúsculas**: `mA` (miliamperio) es real, `ma` (un `mg` mal leído) no; `M`
  (molar) no es `m` (metro). Unidades escritas todas en mayúsculas (`MG/KG`) se aceptan.
- `gr` es ambiguo (grain = 64.8 mg en inglés; "gramo" en español): es real, pero el agente
  debe advertir la ambigüedad.
- El catálogo solo **clasifica**; no corrige números mal leídos ni tablas desalineadas. La
  protección final es que el agente cite la fuente.
- Piloto: las mismas 18 correcciones y 2 errores de OCR nuevos detectados (`ma/kg` en una
  tabla de ketamina, `yg/dl` en un valor de cortisol).

## D11. Ajustes de la limpieza con el corpus completo (322 documentos)

El piloto no mostró estos casos; aparecieron al revisar el reporte del corpus completo:

| Falso positivo | Ejemplo real | Ajuste |
|---|---|---|
| "Otros nombres" de razas | `Otros nombres: Bobtail Japonés` | La etiqueta `nombres` (plural) ya no cuenta |
| "nombre:" dentro de una oración | `…con el nombre: fibrosis hepatoportal…` | La etiqueta debe ir al inicio de línea, de celda o tras una coma |
| Casos clínicos | `Nombre: Mimo Especie: Felina Raza: Persa Edad: 7 años` | Solo se borra el **valor** de la etiqueta, hasta la siguiente etiqueta: se conservan especie, raza, edad y peso |
| Filas de tablas | `600 3200 6400` | Teléfono sin etiqueta solo con formato inequívoco: `(81) 1234-5678`, `81-1234-5678`, `+52 …` |
| Referencias bibliográficas | `(250) 1996-1998` | Se excluyen rangos de años |
| Unidades reales fuera del catálogo | `mcg/kg`, `units/kg`, `gm/kg`, `3 veces/día`, `mosmol/kg`, `lat/min` | Se agregaron al catálogo |

También se separó la regla "μ griega → µ" (1,099 casos: mismo símbolo, distinto carácter) de
"ug → µg" (736), para que el reporte no infle las correcciones reales.

## D12. Unidades ambiguas: advertir ahora, corregir con revisión médica después

- Las unidades ambiguas (`mi/kg`, `u/kg`, `ig/ml`…) **no se corrigen automáticamente**:
  corregir sería adivinar, y en una dosis eso es peligroso.
- **Ahora**: cada chunk con una unidad dudosa lleva `unidades_dudosas` en sus metadatos. El
  agente siempre cita libro y página cuando responde con dosis o medidas, recomienda verificar
  en la fuente y advierte explícitamente si el fragmento usado tiene una unidad dudosa.
- **Fase 2 (trabajo futuro)**: corrección con revisión humana (*human-in-the-loop*):
  1. Botón "Reportar error" en las respuestas del chat.
  2. Tabla `correcciones` (chunk, texto original/corregido, origen, estado, quién reportó,
     quién revisó, fechas), precargada con las unidades ambiguas de la limpieza.
  3. Panel de administrador donde un médico (rol `admin`) aprueba, edita o rechaza.
  4. Al aprobar, se actualiza el chunk y se vuelve a vectorizar **solo ese chunk**. El texto
     original queda en la tabla, así que la corrección se puede deshacer.
- No es "reentrenar" el modelo: se corrige la **base de conocimiento**, que es más barato,
  inmediato y auditable.

## D13. Tabla de confusiones del OCR

- Se revisaron en contexto las 277 unidades sospechosas del corpus y se clasificaron en 4
  grupos: (1) confusiones sin ambigüedad (`Ul`→`UI`, `rng`→`mg`, `rnl`→`ml`, `mrnol`→`mmol`,
  `rnEq`→`mEq`, `mEg`→`mEq`…); (2) la µ mal leída (`llg`, `IJg`, `jig`, `yg`, `prg`…→`µg`);
  (3) unidades reales que faltaban (`fmol`, `CFU`, `AU`, `microl`, `spz`, `tomas/día`, `ui`…);
  (4) ambiguas (`mi/kg`, `u/kg`, `ig/ml`, `ma/kg`…), que **solo se reportan** (ver D12).
- Regla de la tabla (verificada con una prueba): lo leído **no** es una unidad real y la
  corrección **sí** está en el catálogo.
- `Ul/kg` se revisó en sus 128 apariciones: todas eran Unidades Internacionales (vitamina E,
  insulina, penicilina). El microlitro mal leído aparece como `ul`, no como `Ul`.
- Las pruebas atraparon un caso peligroso: en `(1Jg/ml)` la µ se leyó como "1J"; la regla
  tomaba el "1" como cantidad y producía `1µg/ml`, **inventando un número**. `Jg` se quitó de
  la tabla: es ambiguo.
- Resultado: 330 correcciones nuevas; las sospechosas bajaron de 840 a **448** (en 61
  documentos). Quedan sobre todo ambiguas y una cola larga de casos únicos.

## D14. Lecciones de la vectorización del corpus completo

- **Sin método de pago, Voyage limita a 3 peticiones y 10 mil tokens por minuto** (el corpus
  habría tardado más de 4 días). Con tarjeta registrada, los tokens gratuitos siguen aplicando
  y el límite de seguridad del código impide pasar de 190 M.
- **La estimación de tokens (4 caracteres por token) se queda corta**: ~20 % en promedio, y
  hasta 1.6× en tablas o texto de OCR. Un lote "estimado" en 200 mil tenía 320,121 tokens
  reales y Voyage lo rechazó. Solución: lotes de 150 mil estimados y, si aun así se pasan,
  **partir el lote a la mitad** automáticamente.
- **Error de transacciones**: sin `autocommit`, la primera consulta abre una transacción
  implícita y cada lote se volvía una subtransacción que solo se guardaba al final; al fallar a
  la mitad se perdía todo lo vectorizado (y el registro de tokens). Se corrigió con
  `autocommit=True` y una prueba que verifica, **desde otra conexión**, que cada lote queda
  guardado. La prueba falla con el código anterior y pasa con el corregido.
- Los ~2.71 M de tokens que se enviaron sin quedar registrados se agregaron a mano a
  `uso_voyage` (fila con `chunks = 0`) para que el contador de seguridad sea exacto.
