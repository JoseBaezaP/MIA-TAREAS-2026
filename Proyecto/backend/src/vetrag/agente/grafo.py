"""Cómo se conectan los nodos (el diagrama del agente) y una clase cómoda para usarlo.

```
START → reformular → buscar → evaluar ─┬─(útiles, o sin intentos)→ responder → END
            ▲                          │
            └──(no sirvieron, quedan intentos)┘
```
"""

from collections.abc import Iterator
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from vetrag.agente.estado import Estado, Respuesta
from vetrag.agente.modelo import ModeloLenguaje
from vetrag.agente.nodos import Nodos
from vetrag.agente.recuperador import Recuperador

# Clases propias que el checkpointer puede guardar y volver a leer. LangGraph exige declararlas:
# así, un checkpoint manipulado no puede hacer que se cree cualquier objeto al leerlo.
TIPOS_PERMITIDOS_EN_MEMORIA = [
    ("vetrag.agente.estado", "Fragmento"),
    ("vetrag.agente.estado", "Mensaje"),
    ("vetrag.agente.estado", "Respuesta"),
]


def memoria_en_ram() -> InMemorySaver:
    """Checkpointer en memoria (se pierde al cerrar el programa; en la F4 irá a PostgreSQL)."""
    return InMemorySaver(
        serde=JsonPlusSerializer(allowed_msgpack_modules=TIPOS_PERMITIDOS_EN_MEMORIA)
    )


def construir_grafo(
    nodos: Nodos, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[Estado, None, Estado, Estado]:
    """Arma y compila el grafo. El *checkpointer* guarda el estado de cada conversación."""
    grafo = StateGraph(Estado)
    # Los "type: ignore" de abajo: los tipos de add_node en LangGraph 1.2 no aceptan una función
    # (Estado) -> Estado con mypy --strict; falla igual con el ejemplo mínimo de su documentación.
    grafo.add_node("reformular", nodos.reformular)  # type: ignore[call-overload]
    grafo.add_node("buscar", nodos.buscar)  # type: ignore[call-overload]
    grafo.add_node("evaluar", nodos.evaluar)  # type: ignore[call-overload]
    grafo.add_node("responder", nodos.responder)  # type: ignore[call-overload]

    grafo.add_edge(START, "reformular")
    grafo.add_edge("reformular", "buscar")
    grafo.add_edge("buscar", "evaluar")
    grafo.add_conditional_edges(
        "evaluar", nodos.decidir_siguiente, {"reformular": "reformular", "responder": "responder"}
    )
    grafo.add_edge("responder", END)
    return grafo.compile(checkpointer=checkpointer)


class Agente:
    """Envoltura del grafo: una conversación por ``hilo`` (``thread_id`` de LangGraph)."""

    def __init__(
        self,
        modelo: ModeloLenguaje,
        recuperador: Recuperador,
        fragmentos_por_busqueda: int = 8,
        max_busquedas: int = 2,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        nodos = Nodos(modelo, recuperador, fragmentos_por_busqueda, max_busquedas)
        self.grafo = construir_grafo(nodos, checkpointer or memoria_en_ram())

    @staticmethod
    def _entrada(pregunta: str) -> Estado:
        # Lo propio de cada pregunta se reinicia; "historial" se conserva (se acumula).
        return {"pregunta": pregunta, "busquedas": 0, "consultas_previas": [], "relevantes": []}

    @staticmethod
    def _configuracion(hilo: str) -> RunnableConfig:
        return {"configurable": {"thread_id": hilo}}

    def preguntar(self, pregunta: str, hilo: str) -> Respuesta:
        """Hace una pregunta dentro de la conversación ``hilo`` y devuelve la respuesta."""
        estado = self.grafo.invoke(self._entrada(pregunta), self._configuracion(hilo))
        return cast(Respuesta, estado["respuesta"])

    def preguntar_paso_a_paso(self, pregunta: str, hilo: str) -> Iterator[tuple[str, Estado]]:
        """Igual que ``preguntar``, pero entrega ``(nodo, cambios)`` al terminar cada nodo: sirve
        para mostrar en pantalla qué está haciendo el agente."""
        for evento in self.grafo.stream(
            self._entrada(pregunta), self._configuracion(hilo), stream_mode="updates"
        ):
            yield from cast(dict[str, Estado], evento).items()
