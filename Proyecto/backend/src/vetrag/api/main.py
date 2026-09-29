"""Aplicación FastAPI: API del agente + archivos estáticos del frontend (un solo servidor).

``uv run vetrag-api`` → http://127.0.0.1:8000 (documentación automática en /docs).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vetrag.agente.grafo import Agente
from vetrag.agente.modelo import ModeloOpenAI
from vetrag.agente.recuperador import RecuperadorPgvector, crear_pool
from vetrag.api import chat
from vetrag.auth import rutas as rutas_auth
from vetrag.auth.limitador import LimitadorIntentos
from vetrag.auth.usuarios import RepositorioUsuarios
from vetrag.config import Configuracion, obtener_configuracion

logger = logging.getLogger(__name__)


def _verificar(configuracion: Configuracion) -> None:
    faltantes = [
        nombre
        for nombre, valor in (
            ("VETRAG_OPENAI_API_KEY", configuracion.openai_api_key),
            ("VETRAG_VOYAGE_API_KEY", configuracion.voyage_api_key),
            ("VETRAG_DATABASE_URL", configuracion.database_url),
            ("VETRAG_JWT_SECRETO", configuracion.jwt_secreto),
        )
        if valor is None
    ]
    if faltantes:
        raise RuntimeError(f"Faltan en backend/.env: {', '.join(faltantes)}")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Al arrancar: abre el pool de conexiones y arma el agente UNA vez para todas las
    peticiones."""
    configuracion: Configuracion = app.state.configuracion
    _verificar(configuracion)
    assert configuracion.database_url and configuracion.openai_api_key
    assert configuracion.voyage_api_key and configuracion.jwt_secreto
    with crear_pool(configuracion.database_url.get_secret_value()) as pool:
        app.state.usuarios = RepositorioUsuarios(pool)
        app.state.usuarios.crear_esquema()
        app.state.jwt_secreto = configuracion.jwt_secreto.get_secret_value()
        app.state.limitador = LimitadorIntentos()
        app.state.agente = Agente(
            modelo=ModeloOpenAI(
                configuracion.openai_api_key.get_secret_value(),
                configuracion.modelo_llm,
                configuracion.esfuerzo_razonamiento,
            ),
            recuperador=RecuperadorPgvector(
                pool,
                configuracion.voyage_api_key.get_secret_value(),
                configuracion.modelo_embedding,
            ),
            fragmentos_por_busqueda=configuracion.fragmentos_por_busqueda,
            max_busquedas=configuracion.max_busquedas,
        )
        yield


def crear_app(
    configuracion: Configuracion | None = None, con_ciclo_de_vida: bool = True
) -> FastAPI:
    """Arma la aplicación. Las pruebas la crean sin ciclo de vida y con dependencias falsas."""
    app = FastAPI(
        title="VetRAG",
        description="Agente veterinario con RAG agéntico: responde con la biblioteca y cita.",
        lifespan=ciclo_de_vida if con_ciclo_de_vida else None,
    )
    app.state.configuracion = configuracion or obtener_configuracion()
    app.include_router(rutas_auth.enrutador)
    app.include_router(chat.enrutador)

    @app.get("/api/salud", tags=["sistema"])
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    # El frontend compilado (Astro) se sirve desde el mismo servidor: mismo origen, así la
    # cookie de sesión funciona sin configurar CORS.
    frontend = app.state.configuracion.ruta_frontend
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    else:
        logger.warning("No existe %s: corre `npm run build` en frontend/", frontend)
    return app


def main() -> None:
    """``vetrag-api``: levanta el servidor en local."""
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("vetrag.api.main:crear_app", factory=True, host="127.0.0.1", port=8000)
