#!/usr/bin/env bash
# EN TU MAC: respalda la base local de VetRAG (chunks, vectores, usuarios) en infra/respaldos/.
# El respaldo NO se sube a git (contiene texto de los libros y los hashes de los usuarios).
set -euo pipefail
cd "$(dirname "$0")"
URL="$(grep '^VETRAG_DATABASE_URL=' ../backend/.env | cut -d= -f2-)"
mkdir -p respaldos
ARCHIVO="respaldos/vetrag-$(date +%Y%m%d-%H%M).dump"
echo "→ Respaldando en $ARCHIVO (formato comprimido de pg_dump)…"
pg_dump --format=custom --no-owner --no-privileges --dbname="$URL" --file="$ARCHIVO"
ls -lh "$ARCHIVO"
