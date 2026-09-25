# api/ — F4: API HTTP con FastAPI · ⏳ pendiente

Expone el agente al frontend:

| Endpoint | Descripción |
|---|---|
| `POST /auth/login` | Recibe correo y contraseña, devuelve un JWT |
| `POST /chat` | Pregunta al agente (requiere `Authorization: Bearer <jwt>`) |

La implementación de la autenticación está en `auth/` y no se publica (ver su README).
