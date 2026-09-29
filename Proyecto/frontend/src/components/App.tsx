import { useEffect, useState } from 'preact/hooks'
import { cerrarSesion, quienSoy } from '../lib/api'
import Chat from './Chat'
import Login from './Login'

/** Decide qué pantalla mostrar según haya o no sesión. */
export default function App() {
  // undefined = todavía no sabemos; null = sin sesión; string = correo del usuario
  const [usuario, setUsuario] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    quienSoy().then(setUsuario).catch(() => setUsuario(null))
  }, [])

  if (usuario === undefined) return null
  if (usuario === null) return <Login alEntrar={setUsuario} />
  return (
    <Chat
      usuario={usuario}
      alSalir={async () => {
        await cerrarSesion()
        setUsuario(null)
      }}
      alExpirar={() => setUsuario(null)}
    />
  )
}
