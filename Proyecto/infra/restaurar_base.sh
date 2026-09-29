#!/usr/bin/env bash
# EN EL SERVIDOR: restaura un respaldo en el contenedor "db" de VetRAG.
# Uso (desde infra/):  ./restaurar_base.sh respaldos/vetrag-AAAAMMDD-HHMM.dump
set -euo pipefail
cd "$(dirname "$0")"
ARCHIVO="${1:?Uso: ./restaurar_base.sh respaldos/archivo.dump}"
docker compose up -d db
# La primera vez, PostgreSQL tarda unos segundos en inicializarse: esperar a que acepte conexiones.
echo "→ Esperando a que la base de datos esté lista…"
for _ in $(seq 1 60); do
  docker compose exec -T db pg_isready -U vetrag -d vetrag >/dev/null 2>&1 && break
  sleep 2
done
docker compose exec -T db pg_isready -U vetrag -d vetrag >/dev/null \
  || { echo "✖ La base de datos no respondió en 2 minutos" >&2; exit 1; }
echo "→ Restaurando $ARCHIVO (incluye recrear el índice HNSW: puede tardar varios minutos)…"
docker compose exec -T db pg_restore --username=vetrag --dbname=vetrag \
  --no-owner --no-privileges --clean --if-exists < "$ARCHIVO"
docker compose exec -T db psql -U vetrag -d vetrag -Atc \
  "SELECT 'chunks: ' || count(*) FROM chunks; SELECT 'usuarios: ' || count(*) FROM usuarios;"
