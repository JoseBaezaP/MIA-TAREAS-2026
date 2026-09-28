# VetRAG — Agente veterinario con RAG agéntico

Proyecto final de la Maestría en Inteligencia Artificial.

Un agente que responde preguntas de medicina veterinaria **únicamente con base en una
biblioteca curada de libros y artículos** (español e inglés), citando la fuente
(libro y página) de cada respuesta.

## Arquitectura

```
PDFs ──► F1 Clasificación ──► F2 Ingesta ─────────────────────────────► pgvector
         (qué sirve)          OCR → Markdown → limpieza → chunks → Voyage   │
                                                                             ▼
Usuario ──► F5 Frontend (React) ──► F4 API (FastAPI + JWT) ──► F3 Agente LangGraph
```

| Pieza | Tecnología | Por qué |
|---|---|---|
| OCR | `ocrmypdf` (Tesseract, spa+eng) | Gratuito y local; recupera los PDFs escaneados |
| PDF → Markdown | `anydoc` | Local, rápido, conserva títulos y tablas |
| Embeddings | Voyage AI `voyage-4` | Multilingüe (es/en), dentro de los tokens gratuitos |
| Base vectorial | PostgreSQL + `pgvector` | SQL estándar + búsqueda por similitud |
| LLM | OpenAI `gpt-5.6-luna` | Económico, salidas estructuradas; detrás de un puerto para poder cambiarlo |
| Agente | LangGraph | Flujo explícito como grafo: reformular → buscar → evaluar → responder |
| API | FastAPI | Tipado, asíncrono, documentación automática |

La justificación detallada de cada decisión está en [`docs/decisiones.md`](docs/decisiones.md).

## Fases

| Fase | Carpeta de código | Estado |
|---|---|---|
| F1. Clasificación del corpus | [`backend/src/vetrag/clasificacion`](backend/src/vetrag/clasificacion) | ✅ Completada: 362 archivos → 322 conservados, 40 descartados (revisión manual) |
| F2. Ingesta (OCR, Markdown, chunking, vectorización) | [`backend/src/vetrag/ingesta`](backend/src/vetrag/ingesta) | ✅ Completada: 116,365 chunks en pgvector (12 documentos pendientes de reproceso) |
| F3. Agente LangGraph + evaluación | [`backend/src/vetrag/agente`](backend/src/vetrag/agente) | 🚧 Agente y chat de consola listos; falta la evaluación |
| F4. API + autenticación | [`backend/src/vetrag/api`](backend/src/vetrag/api) | ⏳ Pendiente |
| F5. Frontend React | [`frontend`](frontend) | ⏳ Pendiente |
| F6. Despliegue en EC2 | [`infra`](infra) | ⏳ Pendiente |

## Trabajo futuro (fase 2)

- **Corrección con revisión médica**: botón "Reportar error" en el chat, tabla `correcciones`
  y panel de administrador donde un médico aprueba o corrige unidades y dosis mal
  digitalizadas; al aprobar, solo ese fragmento se vuelve a vectorizar. Ver
  [`docs/decisiones.md`](docs/decisiones.md), D12.
- **Reprocesar los documentos pendientes** y aplicar las mejoras menores registradas en
  [`data/pendientes/`](data/pendientes).

## ¿Qué NO está en este repositorio y por qué?

Este repositorio es público, así que muestra **el proceso y el código** (clasificación,
RAG y agente), pero **no los datos**:

| Excluido | Motivo |
|---|---|
| `assets/` (PDFs) | Libros con derechos de autor, ~14 GB |
| `data/` (resultados intermedios) | Derivados de los PDFs: mismo problema de derechos y tamaño |
| Volcados de la base de datos | Contienen el texto de los libros y los usuarios |
| Módulo `auth/` | Minimiza la superficie expuesta de la autenticación |
| `.env` | API keys y secretos |

Cada carpeta excluida conserva su `README.md`, que explica qué contiene y cómo se genera.

## Estructura

```
Proyecto/
├── assets/     # biblioteca original (no se sube)
├── data/       # resultados de cada fase (no se sube)
├── backend/    # código Python: clasificación, ingesta, agente, API
├── frontend/   # interfaz React (F5)
├── infra/      # Docker, PostgreSQL + pgvector
└── docs/       # decisiones técnicas y documentación
```
