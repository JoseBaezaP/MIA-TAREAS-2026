"""Endpoint del chat: responde en *streaming* (Server-Sent Events) paso por paso.

Cada evento es una línea ``event: <tipo>`` + ``data: <json>``:

- ``paso``: el agente terminó un nodo (``reformular``, ``buscar``, ``evaluar``) → la interfaz
  muestra "Buscando…", "8 fragmentos…", "6 útiles…".
- ``respuesta``: el texto final, las fuentes y las advertencias.
- ``error``: algo falló (la conexión se cierra después).
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from vetrag.agente.estado import Estado, Respuesta
from vetrag.agente.grafo import Agente
from vetrag.auth.rutas import UsuarioActual

logger = logging.getLogger(__name__)
enrutador = APIRouter(prefix="/api", tags=["chat"])


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2_000)
    # Lo genera el navegador; junto con el usuario forma el hilo de la conversación.
    conversacion_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


def evento(tipo: str, datos: dict[str, Any]) -> str:
    """Un evento en formato Server-Sent Events."""
    return f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


def describir_paso(nodo: str, cambios: Estado) -> dict[str, Any]:
    """Lo que la interfaz necesita saber de cada nodo."""
    if nodo == "reformular":
        return {"nodo": nodo, "consulta": cambios.get("consulta", "")}
    if nodo == "buscar":
        return {"nodo": nodo, "fragmentos": len(cambios.get("fragmentos", []))}
    if nodo == "evaluar":
        return {"nodo": nodo, "relevantes": len(cambios.get("relevantes", []))}
    return {"nodo": nodo}


def respuesta_a_json(respuesta: Respuesta) -> dict[str, Any]:
    return {
        "texto": respuesta.texto,
        "encontro_informacion": respuesta.encontro_informacion,
        "advertencias": list(respuesta.advertencias),
        "fuentes": [
            {
                "numero": numero,
                "cita": fragmento.cita,
                "documento": fragmento.documento,
                "especialidad": fragmento.especialidad,
                "seccion": " > ".join(fragmento.ruta_titulos),
                "pagina_inicio": fragmento.pagina_inicio,
                "pagina_fin": fragmento.pagina_fin,
            }
            for numero, fragmento in respuesta.fuentes
        ],
    }


def transmitir(agente: Agente, pregunta: str, hilo: str) -> Iterator[str]:
    """Generador de eventos. FastAPI lo ejecuta en un hilo aparte (el agente es síncrono)."""
    try:
        for nodo, cambios in agente.preguntar_paso_a_paso(pregunta, hilo):
            if nodo == "responder":
                yield evento("respuesta", respuesta_a_json(cambios["respuesta"]))
            else:
                yield evento("paso", describir_paso(nodo, cambios))
    except Exception:  # el detalle queda en el log del servidor, no se muestra al usuario
        logger.exception("Error al responder")
        yield evento("error", {"mensaje": "Ocurrió un error al responder. Intenta de nuevo."})


@enrutador.post("/chat")
def chat(datos: Pregunta, sesion: UsuarioActual, request: Request) -> StreamingResponse:
    """Hace una pregunta al agente. Requiere sesión."""
    # El hilo incluye al usuario: nadie puede continuar la conversación de otra persona aunque
    # conozca su conversacion_id.
    hilo = f"{sesion.usuario_id}:{datos.conversacion_id}"
    return StreamingResponse(
        transmitir(request.app.state.agente, datos.pregunta, hilo),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
