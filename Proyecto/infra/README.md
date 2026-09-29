# infra/ — F6: Despliegue en EC2

```
Internet ──HTTPS──► nginx del servidor ──► 127.0.0.1:8000 ──► contenedor app (FastAPI + frontend)
                    (también sirve otros                          │ red interna de docker compose
                     sitios, p. ej. Laravel)                      ▼
                                                             contenedor db (PostgreSQL 17 + pgvector)
```

| Archivo | Qué es |
|---|---|
| `../Dockerfile` | Imagen en 2 etapas: Node compila el frontend; Python 3.12 + uv corre la API (sin Node en la imagen final, usuario sin privilegios) |
| `docker-compose.yml` | `app` + `db` (pgvector propio de VetRAG). La base no tiene puertos publicados; la app solo escucha en `127.0.0.1` |
| `.env.example` | Variables del servidor (copiar a `infra/.env`, que no se sube) |
| `nginx-vetrag.conf` | Bloque de nginx con `proxy_buffering off` para el chat en streaming |
| `respaldar_base.sh` | **En la Mac**: `pg_dump` de la base local → `respaldos/` (no se sube a git) |
| `restaurar_base.sh` | **En el servidor**: `pg_restore` en el contenedor `db` |
| `publicar_privado.sh` | **En la Mac**: publica el código completo (con `auth/`) en el repo privado |

## Pasos

**En la Mac**
```bash
infra/publicar_privado.sh "mensaje"          # código → repo privado
infra/respaldar_base.sh                      # base → infra/respaldos/vetrag-….dump (~620 MB)
scp infra/respaldos/vetrag-….dump SERVIDOR:~/vetrag/infra/respaldos/
```

**En el servidor (primera vez)**
```bash
git clone git@github.com:JoseBaezaP/vetrag.git ~/vetrag && cd ~/vetrag/infra
cp .env.example .env && nano .env            # contraseñas, API keys, JWT, usuarios
./restaurar_base.sh respaldos/vetrag-….dump  # chunks + vectores + usuarios
docker compose up -d --build                 # construye y arranca
docker compose exec app vetrag-usuarios sincronizar

sudo cp nginx-vetrag.conf /etc/nginx/sites-available/vetrag   # cambiar el dominio
sudo ln -s /etc/nginx/sites-available/vetrag /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d vetrag.TU-DOMINIO.com                 # HTTPS
```

**Actualizaciones**
```bash
cd ~/vetrag && git pull && cd infra && docker compose up -d --build
```

## ¿Por qué no se suben los datos?

`respaldos/` y el volumen de la base contienen el texto de los libros y los hashes de los
usuarios. Se copian directamente al servidor con `scp`, nunca por git.
