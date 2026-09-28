"""Los nodos del grafo: cada uno recibe el estado y devuelve **solo lo que cambia**.

``reformular`` y ``evaluar`` piden salidas estructuradas (Pydantic) para que el código pueda
decidir; ``responder`` pide texto libre. Las fuentes y las advertencias de la respuesta final las
arma el **código**, no el LLM, para que siempre sean exactas.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from vetrag.agente import prompts
from vetrag.agente.estado import Estado, Fragmento, Mensaje, Respuesta
from vetrag.agente.modelo import ModeloLenguaje
from vetrag.agente.recuperador import Recuperador

TURNOS_DE_HISTORIAL = 6  # últimos mensajes que se le dan al LLM para entender el contexto
CARACTERES_POR_FRAGMENTO = 2_500  # recorte al mostrarle un fragmento al LLM
_PATRON_CITA = re.compile(r"\[(\d+)\]")


# --- Salidas estructuradas --------------------------------------------------------------------


class Consulta(BaseModel):
    """Salida de ``reformular``."""

    consulta: str = Field(description="Consulta de búsqueda autocontenida y concisa")


class Evaluacion(BaseModel):
    """Salida de ``evaluar``."""

    utiles: list[int] = Field(description="Números de los fragmentos útiles (puede estar vacía)")
    motivo: str = Field(description="Explicación breve de la decisión")


# --- Funciones auxiliares (puras) ---------------------------------------------------------------


def historial_como_mensajes(historial: Sequence[Mensaje]) -> list[dict[str, str]]:
    """Los últimos turnos en el formato de mensajes del LLM."""
    return [{"role": m.rol, "content": m.contenido} for m in historial[-TURNOS_DE_HISTORIAL:]]


def formatear_fragmentos(fragmentos: Sequence[Fragmento]) -> str:
    """Fragmentos numerados, con su cita y la marca de unidades dudosas, para el LLM."""
    bloques = []
    for numero, f in enumerate(fragmentos, start=1):
        seccion = " > ".join(f.ruta_titulos) or "sin sección"
        encabezado = f"[{numero}] {f.cita} — {seccion}"
        if f.unidades_dudosas:
            encabezado += f"\nUNIDADES DUDOSAS: {'; '.join(f.unidades_dudosas)}"
        bloques.append(f"{encabezado}\n{f.texto[:CARACTERES_POR_FRAGMENTO]}")
    return "\n\n---\n\n".join(bloques)


def citas_usadas(texto: str, total: int) -> list[int]:
    """Números de cita ``[n]`` que aparecen en el texto (sin repetir, en orden)."""
    vistos: list[int] = []
    for coincidencia in _PATRON_CITA.finditer(texto):
        numero = int(coincidencia.group(1))
        if 1 <= numero <= total and numero not in vistos:
            vistos.append(numero)
    return vistos


def advertencias_de_unidades(fuentes: Sequence[tuple[int, Fragmento]]) -> tuple[str, ...]:
    """Una advertencia por cada fuente citada que tiene unidades dudosas."""
    return tuple(
        f"[{numero}] {f.cita}: la unidad en «{unidad}» puede estar mal digitalizada; "
        "verifícala en el libro."
        for numero, f in fuentes
        for unidad in f.unidades_dudosas
    )


# --- Nodos ------------------------------------------------------------------------------------


@dataclass
class Nodos:
    """Los nodos del grafo, con sus dependencias (el modelo y el recuperador) ya inyectadas."""

    modelo: ModeloLenguaje
    recuperador: Recuperador
    fragmentos_por_busqueda: int = 8
    max_busquedas: int = 2

    def reformular(self, estado: Estado) -> Estado:
        """Convierte la pregunta (y el contexto de la conversación) en una consulta de búsqueda."""
        previas = estado.get("consultas_previas", [])
        pedido = f"Pregunta: {estado['pregunta']}"
        if previas:
            pedido += "\nConsultas anteriores SIN resultados útiles: " + "; ".join(previas)
        mensajes = [
            *historial_como_mensajes(estado.get("historial", [])),
            {"role": "user", "content": pedido},
        ]
        salida = self.modelo.generar_estructurado(prompts.REFORMULAR, mensajes, Consulta)
        return {"consulta": salida.consulta, "consultas_previas": [*previas, salida.consulta]}

    def buscar(self, estado: Estado) -> Estado:
        """Busca en pgvector los fragmentos más parecidos a la consulta."""
        fragmentos = self.recuperador.buscar(estado["consulta"], self.fragmentos_por_busqueda)
        return {"fragmentos": fragmentos, "busquedas": estado.get("busquedas", 0) + 1}

    def evaluar(self, estado: Estado) -> Estado:
        """Decide qué fragmentos sirven para responder (filtra otros temas y texto dañado)."""
        fragmentos = estado.get("fragmentos", [])
        if not fragmentos:
            return {"relevantes": []}
        mensajes = [
            {
                "role": "user",
                "content": f"Pregunta: {estado['pregunta']}\n\n"
                f"Fragmentos:\n\n{formatear_fragmentos(fragmentos)}",
            }
        ]
        salida = self.modelo.generar_estructurado(prompts.EVALUAR, mensajes, Evaluacion)
        utiles = [n for n in dict.fromkeys(salida.utiles) if 1 <= n <= len(fragmentos)]
        return {"relevantes": [fragmentos[n - 1] for n in utiles]}

    def decidir_siguiente(self, estado: Estado) -> Literal["reformular", "responder"]:
        """Arista condicional: ¿se responde o se busca otra vez con otra consulta?"""
        if estado.get("relevantes") or estado.get("busquedas", 0) >= self.max_busquedas:
            return "responder"
        return "reformular"

    def responder(self, estado: Estado) -> Estado:
        """Redacta la respuesta citando los fragmentos; las fuentes las arma el código."""
        relevantes = estado.get("relevantes", [])
        pregunta = estado["pregunta"]
        if not relevantes:
            respuesta = Respuesta(prompts.SIN_INFORMACION, encontro_informacion=False)
        else:
            mensajes = [
                *historial_como_mensajes(estado.get("historial", [])),
                {
                    "role": "user",
                    "content": f"Fragmentos de la biblioteca:\n\n{formatear_fragmentos(relevantes)}"
                    f"\n\n---\n\nPregunta: {pregunta}",
                },
            ]
            texto = self.modelo.generar(prompts.RESPONDER, mensajes)
            numeros = citas_usadas(texto, len(relevantes)) or list(range(1, len(relevantes) + 1))
            fuentes = tuple((n, relevantes[n - 1]) for n in sorted(numeros))
            respuesta = Respuesta(texto, fuentes, advertencias_de_unidades(fuentes))
        return {
            "respuesta": respuesta,
            "historial": [Mensaje("user", pregunta), Mensaje("assistant", respuesta.texto)],
        }
