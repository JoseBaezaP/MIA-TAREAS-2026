"""El modelo de lenguaje: un **puerto** (lo que el agente necesita) y su adaptador de OpenAI.

Los nodos solo conocen ``ModeloLenguaje``. Cambiar a otro proveedor o a LangChain es escribir
otro adaptador con los mismos dos métodos, sin tocar el grafo. Las pruebas usan un modelo falso.
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar, cast

from openai import OpenAI
from openai.types.responses import ResponseInputParam
from openai.types.shared import ReasoningEffort
from openai.types.shared_params import Reasoning
from pydantic import BaseModel

Esquema = TypeVar("Esquema", bound=BaseModel)


class ModeloLenguaje(Protocol):
    """Lo que el agente necesita de un LLM."""

    def generar(self, instrucciones: str, mensajes: Sequence[dict[str, str]]) -> str:
        """Texto libre (la respuesta final)."""
        ...

    def generar_estructurado(
        self, instrucciones: str, mensajes: Sequence[dict[str, str]], esquema: type[Esquema]
    ) -> Esquema:
        """Un objeto con la forma de ``esquema`` (Pydantic): para que el código pueda decidir."""
        ...


class ModeloOpenAI:
    """Adaptador con el SDK oficial de OpenAI (API *Responses*)."""

    def __init__(self, api_key: str, modelo: str, esfuerzo_razonamiento: str = "low") -> None:
        self._cliente = OpenAI(api_key=api_key)
        self._modelo = modelo
        self._razonamiento: Reasoning = {"effort": cast(ReasoningEffort, esfuerzo_razonamiento)}

    @staticmethod
    def _entrada(mensajes: Sequence[dict[str, str]]) -> ResponseInputParam:
        # Nuestros mensajes {"role", "content"} tienen la forma de los de la API.
        return cast(ResponseInputParam, list(mensajes))

    def generar(self, instrucciones: str, mensajes: Sequence[dict[str, str]]) -> str:
        respuesta = self._cliente.responses.create(
            model=self._modelo,
            instructions=instrucciones,
            input=self._entrada(mensajes),
            reasoning=self._razonamiento,
        )
        return respuesta.output_text

    def generar_estructurado(
        self, instrucciones: str, mensajes: Sequence[dict[str, str]], esquema: type[Esquema]
    ) -> Esquema:
        respuesta = self._cliente.responses.parse(
            model=self._modelo,
            instructions=instrucciones,
            input=self._entrada(mensajes),
            reasoning=self._razonamiento,
            text_format=esquema,
        )
        if respuesta.output_parsed is None:
            raise ValueError("El modelo no devolvió una salida con el formato esperado")
        return respuesta.output_parsed
