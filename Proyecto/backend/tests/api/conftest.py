"""App de prueba: sin base de datos ni APIs reales (agente y usuarios falsos)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.agente.test_agente import ModeloFalso, RecuperadorFalso
from vetrag.agente.grafo import Agente
from vetrag.api.main import crear_app
from vetrag.auth.limitador import LimitadorIntentos
from vetrag.auth.seguridad import hashear_contrasena
from vetrag.auth.usuarios import Usuario
from vetrag.config import Configuracion

CONTRASENA = "Moquillo-parvo-1234"


class RepositorioUsuariosFalso:
    def __init__(self) -> None:
        self.usuarios = {
            "ana@example.com": Usuario(1, "ana@example.com", hashear_contrasena(CONTRASENA), True),
            "baja@example.com": Usuario(
                2, "baja@example.com", hashear_contrasena(CONTRASENA), False
            ),
        }

    def obtener_por_email(self, email: str) -> Usuario | None:
        return self.usuarios.get(email.strip().lower())

    def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        return next((u for u in self.usuarios.values() if u.id == usuario_id), None)


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[TestClient]:
    configuracion = Configuracion(ruta_frontend=tmp_path / "no-existe", horas_de_sesion=1)
    app = crear_app(configuracion, con_ciclo_de_vida=False)
    app.state.usuarios = RepositorioUsuariosFalso()
    app.state.jwt_secreto = "s" * 64
    app.state.limitador = LimitadorIntentos(maximo=3)
    app.state.agente = Agente(ModeloFalso(utiles_por_intento=[[1]] * 10), RecuperadorFalso())
    with TestClient(app) as c:
        yield c


def iniciar_sesion(cliente: TestClient) -> None:
    r = cliente.post("/api/auth/login", json={"email": "Ana@Example.com", "password": CONTRASENA})
    assert r.status_code == 200
