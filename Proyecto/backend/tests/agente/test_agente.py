"""Pruebas del agente con un modelo y un recuperador FALSOS: recorren todos los caminos del
grafo sin llamar a OpenAI, a Voyage ni a la base de datos."""

from collections.abc import Callable, Sequence

import pytest
from pydantic import BaseModel

from vetrag.agente import prompts
from vetrag.agente.estado import Fragmento, Mensaje
from vetrag.agente.grafo import Agente
from vetrag.agente.nodos import (
    Consulta,
    Evaluacion,
    advertencias_de_unidades,
    citas_usadas,
    formatear_fragmentos,
    historial_como_mensajes,
)


def fragmento(numero: int, dudosas: tuple[str, ...] = ()) -> Fragmento:
    return Fragmento(
        id=f"f{numero}", documento=f"Libro {numero}", especialidad="Endocrino",
        ruta_titulos=("Cushing", "Diagnóstico"), pagina_inicio=10 + numero,
        pagina_fin=10 + numero, texto=f"Texto del fragmento {numero}.", similitud=0.7,
        unidades_dudosas=dudosas,
    )  # fmt: skip


class ModeloFalso:
    """Responde según reglas simples y guarda lo que recibió."""

    def __init__(
        self,
        utiles_por_intento: Sequence[list[int]],
        respuesta: str = "El diagnóstico se confirma con la prueba de ACTH [1].",
    ) -> None:
        self.utiles_por_intento = list(utiles_por_intento)
        self.respuesta = respuesta
        self.consultas: list[str] = []
        self.ultimos_mensajes: list[dict[str, str]] = []
        self.mensajes_reformular: list[list[dict[str, str]]] = []

    def generar(self, instrucciones: str, mensajes: Sequence[dict[str, str]]) -> str:
        self.ultimos_mensajes = list(mensajes)
        return self.respuesta

    def generar_estructurado[T: BaseModel](
        self, instrucciones: str, mensajes: Sequence[dict[str, str]], esquema: type[T]
    ) -> T:
        if esquema is Consulta:
            consulta = f"consulta {len(self.consultas) + 1}"
            self.consultas.append(consulta)
            self.mensajes_reformular.append(list(mensajes))
            return esquema.model_validate({"consulta": consulta})
        utiles = self.utiles_por_intento.pop(0) if self.utiles_por_intento else []
        return esquema.model_validate({"utiles": utiles, "motivo": "prueba"})


class RecuperadorFalso:
    def __init__(self, crear: Callable[[int], Fragmento] = fragmento) -> None:
        self.consultas: list[str] = []
        self.crear = crear

    def buscar(self, consulta: str, cantidad: int) -> list[Fragmento]:
        self.consultas.append(consulta)
        return [self.crear(i) for i in range(1, 4)]


def agente(modelo: ModeloFalso, recuperador: RecuperadorFalso | None = None) -> Agente:
    return Agente(modelo, recuperador or RecuperadorFalso(), fragmentos_por_busqueda=3)


# --- Caminos del grafo ------------------------------------------------------------------------


def test_camino_directo_encuentra_y_responde() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[1, 3]])
    respuesta = agente(modelo).preguntar("¿Cómo se diagnostica Cushing?", "hilo")
    assert respuesta.encontro_informacion
    assert "[1]" in respuesta.texto
    assert [n for n, _ in respuesta.fuentes] == [1]  # solo lo que se citó
    assert respuesta.fuentes[0][1].documento == "Libro 1"
    assert modelo.consultas == ["consulta 1"]  # una sola búsqueda


def test_si_nada_sirve_reformula_y_busca_otra_vez() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[], [2]])
    recuperador = RecuperadorFalso()
    respuesta = agente(modelo, recuperador).preguntar("¿Cushing?", "hilo")
    assert recuperador.consultas == ["consulta 1", "consulta 2"]
    assert respuesta.encontro_informacion
    # La segunda reformulación sabe que la primera consulta no sirvió.
    assert "consulta 1" in modelo.mensajes_reformular[1][-1]["content"]


def test_sin_informacion_despues_de_los_intentos() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[], []])
    recuperador = RecuperadorFalso()
    respuesta = agente(modelo, recuperador).preguntar("¿Algo que no está?", "hilo")
    assert len(recuperador.consultas) == 2  # max_busquedas = 2
    assert not respuesta.encontro_informacion
    assert respuesta.texto == prompts.SIN_INFORMACION
    assert respuesta.fuentes == ()


def test_advierte_unidades_dudosas_de_las_fuentes_citadas() -> None:
    recuperador = RecuperadorFalso(crear=lambda i: fragmento(i, ("0,5-1 ma/kg",) if i == 1 else ()))
    modelo = ModeloFalso(utiles_por_intento=[[1, 2]], respuesta="Ketamina 0,5-1 ma/kg [1].")
    respuesta = agente(modelo, recuperador).preguntar("¿Dosis de ketamina?", "hilo")
    assert len(respuesta.advertencias) == 1
    assert "ma/kg" in respuesta.advertencias[0]
    # Al LLM también se le avisó en el texto de los fragmentos.
    assert "UNIDADES DUDOSAS" in modelo.ultimos_mensajes[-1]["content"]


def test_recuerda_la_conversacion_en_el_mismo_hilo() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[1], [1]])
    asistente = agente(modelo)
    asistente.preguntar("¿Dosis de meloxicam en perros?", "hilo A")
    asistente.preguntar("¿Y en gatos?", "hilo A")
    contenidos = [m["content"] for m in modelo.ultimos_mensajes]
    assert "¿Dosis de meloxicam en perros?" in contenidos  # la pregunta anterior llegó al LLM


def test_hilos_distintos_no_comparten_conversacion() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[1], [1]])
    asistente = agente(modelo)
    asistente.preguntar("¿Dosis de meloxicam en perros?", "hilo A")
    asistente.preguntar("¿Y en gatos?", "hilo B")
    contenidos = [m["content"] for m in modelo.ultimos_mensajes]
    assert "¿Dosis de meloxicam en perros?" not in contenidos


def test_paso_a_paso_recorre_los_nodos_en_orden() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[], [1]])
    pasos = [nodo for nodo, _ in agente(modelo).preguntar_paso_a_paso("¿Cushing?", "hilo")]
    assert pasos == [
        "reformular", "buscar", "evaluar", "reformular", "buscar", "evaluar", "responder",
    ]  # fmt: skip


def test_ignora_numeros_de_fragmento_inventados_por_el_llm() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[1, 7, 1]], respuesta="Dato [1] y [9].")
    respuesta = agente(modelo).preguntar("¿Cushing?", "hilo")
    assert [n for n, _ in respuesta.fuentes] == [1]


# --- Funciones auxiliares ---------------------------------------------------------------------


def test_cita_del_fragmento() -> None:
    assert fragmento(1).cita == "Libro 1, pág. 11"
    rango = Fragmento("x", "Libro", "", (), 3, 5, "t", 0.5)
    assert rango.cita == "Libro, págs. 3-5"
    assert Fragmento("x", "Sangre", "", (), None, None, "t", 0.5).cita == "Sangre"


def test_citas_usadas() -> None:
    assert citas_usadas("Uno [2], dos [1] y otra vez [2]; inventada [8].", total=3) == [2, 1]


def test_formatear_fragmentos_marca_unidades_dudosas() -> None:
    texto = formatear_fragmentos([fragmento(1), fragmento(2, ("5 ma/kg",))])
    assert texto.startswith("[1] Libro 1, pág. 11 — Cushing > Diagnóstico")
    assert "UNIDADES DUDOSAS: 5 ma/kg" in texto


def test_historial_limitado_a_los_ultimos_turnos() -> None:
    historial = [Mensaje("user", str(i)) for i in range(10)]
    assert [m["content"] for m in historial_como_mensajes(historial)] == [
        "4", "5", "6", "7", "8", "9",
    ]  # fmt: skip


def test_advertencias_de_unidades() -> None:
    advertencias = advertencias_de_unidades([(2, fragmento(2, ("1a/kg/h",)))])
    assert advertencias[0].startswith("[2] Libro 2, pág. 12")


@pytest.mark.parametrize("esquema", [Consulta, Evaluacion])
def test_esquemas_estructurados_validan(esquema: type[BaseModel]) -> None:
    datos = {"consulta": "x"} if esquema is Consulta else {"utiles": [1], "motivo": "m"}
    assert esquema.model_validate(datos)


def test_fuentes_ordenadas_por_numero() -> None:
    modelo = ModeloFalso(utiles_por_intento=[[1, 2, 3]], respuesta="A [3], B [1], C [2].")
    respuesta = agente(modelo).preguntar("¿Cushing?", "hilo")
    assert [n for n, _ in respuesta.fuentes] == [1, 2, 3]


def test_memoria_sin_avisos_de_tipos_no_registrados(caplog: pytest.LogCaptureFixture) -> None:
    asistente = agente(ModeloFalso(utiles_por_intento=[[1], [1]]))
    asistente.preguntar("¿Dosis de meloxicam?", "hilo")
    asistente.preguntar("¿Y en gatos?", "hilo")  # lee el checkpoint anterior
    assert "unregistered type" not in caplog.text
