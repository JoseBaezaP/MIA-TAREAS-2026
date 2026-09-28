"""Tipos de datos del agente: el estado que viaja por el grafo y los fragmentos recuperados."""

import operator
from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict


@dataclass(frozen=True, slots=True)
class Fragmento:
    """Un chunk recuperado de la base de conocimiento, con lo necesario para citarlo."""

    id: str
    documento: str
    especialidad: str
    ruta_titulos: tuple[str, ...]
    pagina_inicio: int | None
    pagina_fin: int | None
    texto: str
    similitud: float
    unidades_dudosas: tuple[str, ...] = ()

    @property
    def cita(self) -> str:
        """``Documento, págs. 12-13`` (o sin páginas si el documento no las tiene)."""
        if self.pagina_inicio is None:
            return self.documento
        if self.pagina_fin in (None, self.pagina_inicio):
            return f"{self.documento}, pág. {self.pagina_inicio}"
        return f"{self.documento}, págs. {self.pagina_inicio}-{self.pagina_fin}"


@dataclass(frozen=True, slots=True)
class Mensaje:
    """Un turno de la conversación."""

    rol: Literal["user", "assistant"]
    contenido: str


@dataclass(frozen=True, slots=True)
class Respuesta:
    """La respuesta final con sus fuentes y advertencias (armadas por código, no por el LLM)."""

    texto: str
    fuentes: tuple[tuple[int, Fragmento], ...] = ()  # (número de cita, fragmento)
    advertencias: tuple[str, ...] = field(default_factory=tuple)
    encontro_informacion: bool = True


class Estado(TypedDict, total=False):
    """La "mochila" que comparten los nodos del grafo.

    ``historial`` usa ``operator.add`` como *reducer*: lo que devuelve un nodo se **agrega** a la
    lista en lugar de reemplazarla. Con el *checkpointer*, así se acumula la conversación entre
    preguntas. El resto de los campos se reemplazan en cada pregunta.
    """

    historial: Annotated[list[Mensaje], operator.add]
    pregunta: str
    consulta: str
    consultas_previas: list[str]
    fragmentos: list[Fragmento]
    relevantes: list[Fragmento]
    busquedas: int
    respuesta: Respuesta
