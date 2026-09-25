# backend/ — Código Python del proyecto

Paquete `vetrag` con una carpeta por fase:

| Carpeta | Fase |
|---|---|
| [`src/vetrag/clasificacion`](src/vetrag/clasificacion) | F1. Clasificación del corpus |
| [`src/vetrag/ingesta`](src/vetrag/ingesta) | F2. OCR, Markdown, chunking y vectorización |
| [`src/vetrag/base_datos`](src/vetrag/base_datos) | Conexión y tablas de PostgreSQL + pgvector |
| [`src/vetrag/agente`](src/vetrag/agente) | F3. Agente LangGraph |
| [`src/vetrag/api`](src/vetrag/api) | F4. API FastAPI |
| [`src/vetrag/auth`](src/vetrag/auth) | F4. Autenticación (no se publica) |
| `tests/` | Pruebas, con la misma estructura que `src/` |

## Requisitos

- Python ≥ 3.12 y [uv](https://docs.astral.sh/uv/)

## Instalación

```bash
cd backend
uv sync
cp .env.example .env   # y completar los valores
```

## Comandos

```bash
uv run vetrag-clasificar          # F1: genera data/01_clasificacion/
uv run pytest                     # pruebas
uv run ruff check . && uv run ruff format --check .   # estilo (PEP 8)
uv run mypy src                   # tipos
```

## Convenciones

- PEP 8, verificado con `ruff`; *type hints* en todo el código (`mypy --strict`).
- `pathlib` para las rutas y `logging` en lugar de `print`.
- La configuración y los secretos solo en `.env`, que se lee con `pydantic-settings`.
- Un archivo de pruebas por módulo en `tests/`.
