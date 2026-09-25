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
- El piloto usa una base local en Docker. Para producción, la base se copia al EC2
  (`pg_dump` / `pg_restore`).

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
