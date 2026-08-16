#!/usr/bin/env bash
# ─── GRACIA — Entrypoint ──────────────────────────────────────
# - Ejecuta las migraciones de Alembic solo en una base nueva (sin tablas),
#   para no romper instalaciones existentes que usan create_all + migración runtime.
# - Arranca uvicorn con un solo worker por defecto (Socket.IO usa memoria).
set -euo pipefail

cd /app/backend

echo ">>> [entrypoint] Verificando base de datos..."

TABLE_COUNT=$(python - <<'PY'
from database import engine
from sqlalchemy import inspect
print(len(inspect(engine).get_table_names()))
PY
)

if [ "$TABLE_COUNT" -eq 0 ]; then
  echo ">>> [entrypoint] Base vacía — aplicando migraciones Alembic"
  alembic upgrade head
else
  echo ">>> [entrypoint] Base existente (${TABLE_COUNT} tablas) — se omiten migraciones Alembic"
fi

WORKERS="${UVICORN_WORKERS:-1}"
echo ">>> [entrypoint] Arrancando uvicorn (workers=${WORKERS}) en 0.0.0.0:${PORT:-5000}"

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-5000}" \
  --workers "${WORKERS}"
