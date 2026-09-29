#!/usr/bin/env bash
# Publica TODO el código del proyecto en el repositorio PRIVADO (incluido auth/), que es el que
# clona el servidor. Se trabaja en Proyecto/ (repo público, sin auth/) y este script copia a una
# carpeta hermana conectada al repo privado, hace commit y push.
#
# Nunca se copian: la biblioteca (assets/), los datos derivados (data/, salvo los README), los
# .env con credenciales, ni dependencias o archivos generados.
#
# Uso:  infra/publicar_privado.sh "mensaje del commit"
#       VETRAG_SOLO_REVISAR=1 infra/publicar_privado.sh "x"   # muestra qué se subiría
set -euo pipefail

MENSAJE="${1:?Uso: infra/publicar_privado.sh \"mensaje del commit\"}"
ORIGEN="$(cd "$(dirname "$0")/.." && pwd)"                        # .../Proyecto
DESTINO="${VETRAG_REPO_PRIVADO:-$(cd "$ORIGEN/../.." && pwd)/vetrag}"  # .../MIA - Maestria/vetrag
REMOTO="git@github.com:JoseBaezaP/vetrag.git"

if [ ! -d "$DESTINO/.git" ]; then
  echo "→ Clonando el repo privado en $DESTINO"
  git clone "$REMOTO" "$DESTINO"
fi

echo "→ Copiando código de $ORIGEN"
# El orden importa: rsync aplica la PRIMERA regla que coincide.
rsync -a --delete \
  --exclude='/.git' \
  --exclude='/.gitignore' \
  --include='/assets/' --include='/assets/README.md' --exclude='/assets/**' \
  --include='/data/' --include='/data/README.md' \
  --include='/data/*/' --include='/data/*/README.md' --exclude='/data/**' \
  --include='.env.example' --exclude='.env' --exclude='.env.*' \
  --exclude='.venv/' --exclude='node_modules/' --exclude='/frontend/dist/' \
  --exclude='__pycache__/' --exclude='.pytest_cache/' --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' --exclude='/infra/pgdata/' --exclude='/infra/respaldos/' \
  --exclude='*.dump' --exclude='*.sql.gz' --exclude='.DS_Store' \
  "$ORIGEN/" "$DESTINO/"

# El repo privado tiene su PROPIO .gitignore (sin excluir auth/): se escribe si no existe.
if [ ! -f "$DESTINO/.gitignore" ]; then
  cat > "$DESTINO/.gitignore" <<'EOF'
# Repo PRIVADO: todo el código (incluido auth/), pero nunca datos ni credenciales.
/assets/*
!/assets/README.md
/data/*
!/data/README.md
!/data/*/
/data/*/*
!/data/*/README.md
.env
.env.*
!.env.example
*.dump
*.sql.gz
/infra/pgdata/
/infra/respaldos/
.venv/
node_modules/
/frontend/dist/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.DS_Store
*.log
EOF
fi

cd "$DESTINO"
# Repo recién creado (sin commits): la rama principal se llama main.
git rev-parse --verify -q HEAD >/dev/null || git symbolic-ref HEAD refs/heads/main

# Última defensa: si por error hay un .env o una llave, no se sube nada.
if git ls-files --others --cached --exclude-standard | grep -E '(^|/)\.env($|\.)|\.pem$|id_rsa' | grep -v '\.env\.example$'; then
  echo "✖ Se encontraron archivos con posibles credenciales (arriba). No se publica nada." >&2
  exit 1
fi

git add -A
if [ "${VETRAG_SOLO_REVISAR:-0}" = "1" ]; then
  echo "→ Modo revisión: esto se subiría (no se hace commit):"
  git status --short
  exit 0
fi
if git diff --cached --quiet; then
  echo "✔ Sin cambios que publicar"
  exit 0
fi
git commit -q -m "$MENSAJE"
git push -q -u origin HEAD
echo "✔ Publicado: $(git log --oneline -1)"
