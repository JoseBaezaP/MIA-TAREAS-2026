# base_datos/ — PostgreSQL + pgvector

| Archivo | Responsabilidad |
|---|---|
| `esquema.sql` | Tablas `chunks` (texto, metadatos y `vector(1024)`) y `uso_voyage` (tokens reportados por Voyage) |
| `conexion.py` | Conexión y creación del esquema |
| `repositorio_chunks.py` | Guardar lotes de chunks, consultar ids y tokens usados, crear el índice HNSW |

**Desarrollo:** PostgreSQL 14 local, base y usuario `vetrag`, pgvector 0.8.6. La conexión va en
`VETRAG_DATABASE_URL` (en `backend/.env`, que no se sube).

La tabla de usuarios vive en el módulo `auth/`, que no se publica. Los **datos** de las tablas
nunca se suben al repositorio: contienen texto de los libros.
