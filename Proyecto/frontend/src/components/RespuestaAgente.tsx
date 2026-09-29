import DOMPurify from 'dompurify'
import { marked } from 'marked'
import type { Respuesta } from '../lib/api'

/**
 * El texto del agente viene en Markdown (negritas, listas, tablas). Se convierte a HTML con
 * `marked` y se LIMPIA con DOMPurify antes de mostrarlo: así, aunque el texto de un libro
 * trajera código HTML o JavaScript, no se ejecuta en el navegador.
 */
function aHtml(texto: string): string {
  const html = marked.parse(texto, { async: false })
  const conCitas = html.replace(/\[(\d+)\]/g, '<a class="cita" href="#fuente-$1">$1</a>')
  return DOMPurify.sanitize(conCitas)
}

export default function RespuestaAgente({ respuesta }: { respuesta: Respuesta }) {
  return (
    <article class="burbuja-agente">
      <div dangerouslySetInnerHTML={{ __html: aHtml(respuesta.texto) }} />

      {respuesta.advertencias.length > 0 && (
        <div class="advertencias" role="note">
          <strong>⚠️ Verifica en el libro</strong>
          <ul>
            {respuesta.advertencias.map((a) => (
              <li>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {respuesta.fuentes.length > 0 && (
        <section class="fuentes">
          <h3>Fuentes</h3>
          <ol>
            {respuesta.fuentes.map((f) => (
              <li id={`fuente-${f.numero}`}>
                <span class="cita">{f.numero}</span>
                <span>
                  {f.cita}
                  {f.seccion && <div class="seccion">{f.seccion}</div>}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  )
}
