# auth/ — Autenticación (F4) · ⏳ pendiente

Módulo de inicio de sesión de la API. Solo existen tres usuarios (autor, tutor y un usuario
de prueba); **no hay registro público**, así que las cuentas se crean desde la línea de
comandos.

## Diseño

- **Contraseñas**: se guardan como *hash* **argon2** (irreversible), nunca en texto plano.
- **Sesión**: al iniciar sesión, la API emite un **JWT firmado** (HS256) con expiración;
  el frontend lo envía en `Authorization: Bearer <token>` y el endpoint `/chat` lo valida.
- **Transporte**: solo sobre HTTPS en el servidor.
- **Protección**: límite de intentos en `/auth/login`.

## ¿Por qué el código no se sube a GitHub?

El repositorio es público y el objetivo académico del proyecto es el proceso de RAG y el
agente, no la autenticación. Excluir este módulo, junto con la tabla de usuarios, sus
datos y los secretos del `.env`, reduce la superficie expuesta en caso de filtración.
Este README documenta el diseño para que el enfoque se pueda evaluar sin publicar la
implementación.
