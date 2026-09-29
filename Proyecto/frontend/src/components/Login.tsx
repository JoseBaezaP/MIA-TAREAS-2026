import { useState } from 'preact/hooks'
import { iniciarSesion } from '../lib/api'

export default function Login({ alEntrar }: { alEntrar: (email: string) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento: Event) {
    evento.preventDefault()
    setError('')
    setEnviando(true)
    try {
      alEntrar(await iniciarSesion(email, password))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar sesión')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main class="login">
      <form class="login-tarjeta" onSubmit={enviar}>
        <div class="marca">
          <span class="marca-icono" aria-hidden="true">🐾</span> VetRAG
        </div>
        <p>Asistente de consulta basado en una biblioteca de medicina veterinaria.</p>
        <label class="campo">
          Correo
          <input
            type="email"
            autocomplete="username"
            required
            value={email}
            onInput={(e) => setEmail(e.currentTarget.value)}
          />
        </label>
        <label class="campo">
          Contraseña
          <input
            type="password"
            autocomplete="current-password"
            required
            value={password}
            onInput={(e) => setPassword(e.currentTarget.value)}
          />
        </label>
        <button class="boton-primario" type="submit" disabled={enviando}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
        {error && (
          <p class="error" role="alert">
            {error}
          </p>
        )}
      </form>
    </main>
  )
}
