# frontend/ — F5: Interfaz web (Preact + Vite)

Pantalla de inicio de sesión y chat con el agente: muestra los pasos del agente en vivo, la
respuesta con formato, las citas `[n]`, las fuentes (libro, páginas y sección) y las
advertencias de unidades dudosas.

| Archivo | Responsabilidad |
|---|---|
| `src/main.tsx` | Punto de entrada |
| `src/components/App.tsx` | Muestra el login o el chat según haya sesión |
| `src/components/Login.tsx` | Formulario de inicio de sesión |
| `src/components/Chat.tsx` | Conversación, pasos en vivo, "Nueva conversación" |
| `src/components/RespuestaAgente.tsx` | Markdown → HTML **sanitizado con DOMPurify**, citas y fuentes |
| `src/lib/api.ts` | Llamadas a la API; lectura del *streaming* (Server-Sent Events) |
| `src/styles/global.css` | Estilos (modo claro y oscuro) |

**¿Por qué Preact + Vite y no Astro?** Es una sola pantalla totalmente interactiva: Astro
aporta en sitios con mucho contenido estático. Preact tiene la misma API que React (lo aprendido
sirve para React) y pesa poco: la app completa son ~33 KB comprimidos.

**Sesión:** la maneja el servidor con una cookie `httpOnly`; este código nunca ve el token.

## Uso

```bash
npm install
npm run dev     # http://localhost:5173 (las llamadas a /api van a FastAPI en el puerto 8000)
npm run build   # genera dist/, que FastAPI sirve en http://127.0.0.1:8000
```
