# api/ — F4: API HTTP con FastAPI

Expone el agente al frontend y **sirve también el frontend compilado** (`frontend/dist`): un solo
servidor y un solo origen, así la cookie de sesión funciona sin configurar CORS.

| Endpoint | Descripción |
|---|---|
| `POST /api/auth/login` | Correo y contraseña → cookie de sesión (JWT, `httpOnly`, `SameSite=strict`) |
| `POST /api/auth/logout` | Borra la sesión |
| `GET /api/auth/yo` | Usuario de la sesión actual |
| `POST /api/chat` | Pregunta al agente (requiere sesión). Responde en *streaming* (Server-Sent Events): eventos `paso`, `respuesta` y `error` |
| `GET /api/salud` | Estado del servidor |
| `GET /docs` | Documentación interactiva generada por FastAPI |

- El hilo de cada conversación es `usuario_id:conversacion_id`: nadie puede continuar la
  conversación de otra persona.
- El agente y el *pool* de conexiones se crean **una vez** al arrancar (`ciclo_de_vida`).

```bash
uv run vetrag-usuarios sincronizar   # crea/actualiza los usuarios de VETRAG_USUARIOS_INICIALES
uv run vetrag-api                    # http://127.0.0.1:8000
```

La implementación de la autenticación está en `auth/` y no se publica (ver su README).
