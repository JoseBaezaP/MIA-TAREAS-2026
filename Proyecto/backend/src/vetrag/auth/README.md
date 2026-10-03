# auth/ — Autenticación (F4)

Módulo de inicio de sesión de la API. Solo existen unas pocas cuentas (autor, tutor y un
usuario de prueba); **no hay registro público**: las cuentas se definen en
`VETRAG_USUARIOS_INICIALES` (`.env`) y se crean con `vetrag-usuarios sincronizar`.

## Diseño

| Aspecto | Implementación |
|---|---|
| Contraseñas | *Hash* **argon2** (`pwdlib`), nunca en texto plano. En la base solo queda el hash |
| Sesión | **JWT** firmado (HS256, `PyJWT`) con expiración de 8 h, guardado en una **cookie `httpOnly` + `SameSite=strict`**: el JavaScript de la página no puede leerlo y otros sitios no pueden enviarlo |
| Transporte | Solo HTTPS en el servidor (`VETRAG_COOKIE_SEGURA=true`) |
| Fuerza bruta | Máximo 5 intentos fallidos cada 10 minutos por IP y correo (HTTP 429) |
| Enumeración | Mismo mensaje de error exista o no el correo |

| Archivo | Responsabilidad |
|---|---|
| `seguridad.py` | Hash y verificación de contraseñas; creación y validación del JWT |
| `usuarios.py` | Tabla `usuarios` y su repositorio |
| `limitador.py` | Límite de intentos fallidos por ventana de tiempo |
| `rutas.py` | Endpoints `/api/auth/*` y la dependencia `usuario_actual` que protege `/api/chat` |
| `__main__.py` | Comando `vetrag-usuarios sincronizar` |

## ¿Por qué el código no se sube a GitHub?

El repositorio es público y el objetivo académico del proyecto es el proceso de RAG y el
agente, no la autenticación. Excluir este módulo, junto con la tabla de usuarios, sus
datos y los secretos del `.env`, reduce la superficie expuesta. Este README documenta el
diseño para que el enfoque se pueda evaluar sin publicar la implementación; el código completo
está en un repositorio privado.
