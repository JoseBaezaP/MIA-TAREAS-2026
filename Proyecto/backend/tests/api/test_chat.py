"""Pruebas del endpoint del chat (streaming SSE)."""

import json

from fastapi.testclient import TestClient

from tests.api.conftest import iniciar_sesion


def eventos(texto: str) -> list[tuple[str, dict[str, object]]]:
    """Separa la respuesta SSE en (tipo, datos)."""
    salida = []
    for bloque in texto.strip().split("\n\n"):
        tipo = bloque.split("\n")[0].removeprefix("event: ")
        datos = json.loads(bloque.split("\n")[1].removeprefix("data: "))
        salida.append((tipo, datos))
    return salida


def test_salud(cliente: TestClient) -> None:
    assert cliente.get("/api/salud").json() == {"estado": "ok"}


def test_chat_requiere_sesion(cliente: TestClient) -> None:
    r = cliente.post("/api/chat", json={"pregunta": "¿Cushing?", "conversacion_id": "abcdefgh1"})
    assert r.status_code == 401


def test_chat_transmite_pasos_y_respuesta(cliente: TestClient) -> None:
    iniciar_sesion(cliente)
    r = cliente.post("/api/chat", json={"pregunta": "¿Cushing?", "conversacion_id": "abcdefgh1"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    lista = eventos(r.text)
    assert [t for t, _ in lista] == ["paso", "paso", "paso", "respuesta"]
    assert lista[0][1] == {"nodo": "reformular", "consulta": "consulta 1"}
    respuesta = lista[-1][1]
    assert respuesta["fuentes"][0]["cita"] == "Libro 1, pág. 11"  # type: ignore[index]


def test_valida_la_pregunta(cliente: TestClient) -> None:
    iniciar_sesion(cliente)
    vacia = cliente.post("/api/chat", json={"pregunta": "", "conversacion_id": "abcdefgh1"})
    rara = cliente.post("/api/chat", json={"pregunta": "hola", "conversacion_id": "../../x"})
    assert vacia.status_code == 422
    assert rara.status_code == 422
