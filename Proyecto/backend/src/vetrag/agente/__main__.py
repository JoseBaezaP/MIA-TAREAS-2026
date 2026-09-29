"""Chat de consola para probar el agente: ``uv run vetrag-chat``.

Muestra lo que hace el agente en cada paso (reformular, buscar, evaluar, responder) y la
respuesta con sus fuentes. Comandos: ``/nuevo`` (conversación nueva) y ``/salir``.
"""

import logging
import textwrap
import uuid

from vetrag.agente.estado import Estado, Respuesta
from vetrag.agente.grafo import Agente
from vetrag.agente.modelo import ModeloOpenAI
from vetrag.agente.recuperador import RecuperadorPgvector, crear_pool
from vetrag.config import obtener_configuracion

ANCHO = 90
AYUDA = "Escribe tu pregunta. Comandos: /nuevo (conversación nueva), /salir."


def _mostrar_paso(nodo: str, cambios: Estado) -> None:
    if nodo == "reformular":
        print(f"  🔎 Buscando: «{cambios.get('consulta', '')}»")
    elif nodo == "buscar":
        print(f"  📚 {len(cambios.get('fragmentos', []))} fragmentos encontrados")
    elif nodo == "evaluar":
        relevantes = cambios.get("relevantes", [])
        if relevantes:
            print(f"  ✅ {len(relevantes)} son útiles")
        else:
            print("  ⚠️  Ninguno sirve; se intenta con otra búsqueda")


def _mostrar_respuesta(respuesta: Respuesta) -> None:
    print()
    for parrafo in respuesta.texto.splitlines():
        print(textwrap.fill(parrafo, ANCHO, subsequent_indent="  ") if parrafo else "")
    if respuesta.fuentes:
        print("\n📖 Fuentes:")
        for numero, fragmento in respuesta.fuentes:
            print(f"   [{numero}] {fragmento.cita}")
    if respuesta.advertencias:
        print("\n⚠️  Advertencias:")
        for advertencia in respuesta.advertencias:
            print(textwrap.fill(advertencia, ANCHO, initial_indent="   ", subsequent_indent="   "))
    print()


def main() -> None:
    """Inicia el chat."""
    logging.basicConfig(level=logging.WARNING)
    configuracion = obtener_configuracion()
    faltantes = [
        nombre
        for nombre, valor in (
            ("VETRAG_OPENAI_API_KEY", configuracion.openai_api_key),
            ("VETRAG_VOYAGE_API_KEY", configuracion.voyage_api_key),
            ("VETRAG_DATABASE_URL", configuracion.database_url),
        )
        if valor is None
    ]
    if faltantes:
        raise SystemExit(f"Faltan en backend/.env: {', '.join(faltantes)}")
    assert configuracion.openai_api_key and configuracion.voyage_api_key
    assert configuracion.database_url

    with crear_pool(configuracion.database_url.get_secret_value(), maximo=1) as pool:
        agente = Agente(
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
        hilo = str(uuid.uuid4())
        print(f"🐾 VetRAG · {configuracion.modelo_llm}\n{AYUDA}\n")
        while True:
            try:
                pregunta = input("Tú: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not pregunta:
                continue
            if pregunta == "/salir":
                break
            if pregunta == "/nuevo":
                hilo = str(uuid.uuid4())
                print("  (conversación nueva)\n")
                continue
            try:
                for nodo, cambios in agente.preguntar_paso_a_paso(pregunta, hilo):
                    if nodo == "responder":
                        _mostrar_respuesta(cambios["respuesta"])
                    else:
                        _mostrar_paso(nodo, cambios)
            except Exception as error:  # que un fallo de red no cierre el chat
                print(f"  ❌ Error: {error}\n")


if __name__ == "__main__":
    main()
