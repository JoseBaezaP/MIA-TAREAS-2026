// Cliente de la API de VetRAG. La sesión viaja en una cookie httpOnly que pone el servidor:
// este código nunca ve el token (por eso no hay que guardarlo en localStorage).

export interface Fuente {
  numero: number;
  cita: string;
  documento: string;
  especialidad: string;
  seccion: string;
  pagina_inicio: number | null;
  pagina_fin: number | null;
}

export interface Respuesta {
  texto: string;
  encontro_informacion: boolean;
  advertencias: string[];
  fuentes: Fuente[];
}

export type Paso =
  | { nodo: 'reformular'; consulta: string }
  | { nodo: 'buscar'; fragmentos: number }
  | { nodo: 'evaluar'; relevantes: number };

export class NoAutorizado extends Error {}

async function detalleDeError(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json();
    return typeof cuerpo.detail === 'string' ? cuerpo.detail : 'Ocurrió un error';
  } catch {
    return 'Ocurrió un error';
  }
}

/** Usuario de la sesión actual, o `null` si no hay sesión. */
export async function quienSoy(): Promise<string | null> {
  const r = await fetch('/api/auth/yo');
  if (!r.ok) return null;
  return (await r.json()).email;
}

export async function iniciarSesion(email: string, password: string): Promise<string> {
  const r = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(await detalleDeError(r));
  return (await r.json()).email;
}

export async function cerrarSesion(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' });
}

/**
 * Hace una pregunta y va avisando cada paso del agente.
 *
 * La API responde con Server-Sent Events (SSE). `EventSource` del navegador solo permite GET,
 * así que se lee el cuerpo de un `fetch` POST en streaming y se separan los eventos a mano:
 * cada evento es `event: tipo\ndata: {json}\n\n`.
 */
export async function preguntar(
  pregunta: string,
  conversacionId: string,
  alPaso: (paso: Paso) => void,
): Promise<Respuesta> {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pregunta, conversacion_id: conversacionId }),
  });
  if (r.status === 401) throw new NoAutorizado();
  if (!r.ok || !r.body) throw new Error(await detalleDeError(r));

  const lector = r.body.getReader();
  const decodificador = new TextDecoder();
  let pendiente = '';
  while (true) {
    const { value, done } = await lector.read();
    if (done) break;
    pendiente += decodificador.decode(value, { stream: true });
    let fin: number;
    while ((fin = pendiente.indexOf('\n\n')) !== -1) {
      const bloque = pendiente.slice(0, fin);
      pendiente = pendiente.slice(fin + 2);
      const tipo = bloque.match(/^event: (.+)$/m)?.[1];
      const datos = bloque.match(/^data: (.+)$/m)?.[1];
      if (!tipo || !datos) continue;
      const contenido = JSON.parse(datos);
      if (tipo === 'paso') alPaso(contenido as Paso);
      else if (tipo === 'respuesta') return contenido as Respuesta;
      else if (tipo === 'error') throw new Error(contenido.mensaje);
    }
  }
  throw new Error('La conexión se cerró antes de recibir la respuesta');
}
