import { useEffect, useRef, useState } from 'preact/hooks'
import { NoAutorizado, preguntar, type Paso, type Respuesta } from '../lib/api'
import RespuestaAgente from './RespuestaAgente'

type Mensaje =
  | { rol: 'usuario'; texto: string }
  | { rol: 'agente'; respuesta: Respuesta }
  | { rol: 'error'; texto: string }

const SUGERENCIAS = [
  '¿Qué dosis de meloxicam se usa en gatos?',
  '¿Cómo se diagnostica el síndrome de Cushing en perros?',
  '¿Cuál es el tratamiento de la parvovirosis canina?',
  'What are the clinical signs of canine distemper?',
]

function describirPaso(paso: Paso): string {
  if (paso.nodo === 'reformular') return `🔎 Buscando: «${paso.consulta}»`
  if (paso.nodo === 'buscar') return `📚 ${paso.fragmentos} fragmentos encontrados`
  return paso.relevantes > 0
    ? `✅ ${paso.relevantes} son útiles · redactando la respuesta`
    : '⚠️ Ninguno sirve; se intenta con otra búsqueda'
}

interface Props {
  usuario: string
  alSalir: () => void
  alExpirar: () => void
}

export default function Chat({ usuario, alSalir, alExpirar }: Props) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [pasos, setPasos] = useState<string[]>([])
  const [texto, setTexto] = useState('')
  const [pensando, setPensando] = useState(false)
  // El id de la conversación lo genera el navegador; el servidor lo combina con el usuario.
  const [conversacionId, setConversacionId] = useState(() => crypto.randomUUID())
  const fin = useRef<HTMLDivElement>(null)

  useEffect(() => fin.current?.scrollIntoView({ behavior: 'smooth' }), [mensajes, pasos])

  async function enviar(pregunta: string) {
    pregunta = pregunta.trim()
    if (!pregunta || pensando) return
    setTexto('')
    setMensajes((m) => [...m, { rol: 'usuario', texto: pregunta }])
    setPasos([])
    setPensando(true)
    try {
      const respuesta = await preguntar(pregunta, conversacionId, (paso) =>
        setPasos((p) => [...p, describirPaso(paso)]),
      )
      setMensajes((m) => [...m, { rol: 'agente', respuesta }])
    } catch (e) {
      if (e instanceof NoAutorizado) return alExpirar()
      const detalle = e instanceof Error ? e.message : 'Ocurrió un error'
      setMensajes((m) => [...m, { rol: 'error', texto: detalle }])
    } finally {
      setPensando(false)
      setPasos([])
    }
  }

  function nuevaConversacion() {
    setMensajes([])
    setConversacionId(crypto.randomUUID()) // otro hilo: el agente ya no recuerda lo anterior
  }

  return (
    <div class="chat">
      <header class="barra">
        <div class="marca">
          <span class="marca-icono" aria-hidden="true">🐾</span> VetRAG
        </div>
        <div class="barra-acciones">
          <span class="usuario" title={usuario}>
            {usuario}
          </span>
          <button class="boton" onClick={nuevaConversacion} disabled={pensando}>
            Nueva conversación
          </button>
          <button class="boton" onClick={alSalir}>
            Salir
          </button>
        </div>
      </header>

      <main class="mensajes" aria-live="polite">
        <div class="columna">
          {mensajes.length === 0 && (
            <section class="bienvenida">
              <h1>¿En qué te ayudo?</h1>
              Respondo solo con la biblioteca veterinaria y cito libro y página.
              <div class="sugerencias">
                {SUGERENCIAS.map((s) => (
                  <button class="boton" onClick={() => enviar(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </section>
          )}

          {mensajes.map((m) =>
            m.rol === 'usuario' ? (
              <div class="burbuja-usuario">{m.texto}</div>
            ) : m.rol === 'agente' ? (
              <RespuestaAgente respuesta={m.respuesta} />
            ) : (
              <div class="burbuja-agente error" role="alert">
                ❌ {m.texto}
              </div>
            ),
          )}

          {pensando && (
            <div class="burbuja-agente pasos">
              {pasos.length === 0 && <span class="paso-activo">Pensando</span>}
              {pasos.map((p, i) => (
                <span class={i === pasos.length - 1 ? 'paso-activo' : ''}>{p}</span>
              ))}
            </div>
          )}
          <div ref={fin} />
        </div>
      </main>

      <footer class="entrada">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            enviar(texto)
          }}
        >
          <textarea
            rows={1}
            placeholder="Escribe tu pregunta… (Enter envía, Shift+Enter hace salto de línea)"
            value={texto}
            maxLength={2000}
            onInput={(e) => setTexto(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                enviar(texto)
              }
            }}
            aria-label="Pregunta"
          />
          <button class="boton-primario" type="submit" disabled={pensando || !texto.trim()}>
            Enviar
          </button>
        </form>
        <p class="aviso-legal">
          Herramienta de consulta: verifica siempre dosis y medidas en la fuente citada. No
          sustituye el criterio del médico veterinario.
        </p>
      </footer>
    </div>
  )
}
