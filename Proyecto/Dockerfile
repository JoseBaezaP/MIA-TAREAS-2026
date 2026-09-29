# syntax=docker/dockerfile:1
# Imagen de VetRAG: FastAPI + agente + el frontend ya compilado. Se construye en 2 etapas para que
# la imagen final NO lleve Node ni las herramientas de compilación.

# --- Etapa 1: compilar el frontend (Preact + Vite) ------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Etapa 2: la aplicación (Python 3.12 + uv) ------------------------------------------------
FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend

# Primero solo las dependencias (se cachean mientras no cambien pyproject.toml / uv.lock)…
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project
# …y luego el código.
COPY backend/src ./src
RUN uv sync --locked --no-dev
COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENV PATH="/app/backend/.venv/bin:$PATH" \
    VETRAG_RUTA_FRONTEND=/app/frontend/dist
# No correr como root dentro del contenedor.
RUN useradd --create-home --uid 10001 vetrag
USER vetrag

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/salud')"
# --proxy-headers: la IP real del usuario llega de nginx (para el límite de intentos de login).
CMD ["uvicorn", "vetrag.api.main:crear_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
