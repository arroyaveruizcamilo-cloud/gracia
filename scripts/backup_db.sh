#!/usr/bin/env bash
# ─── GRACIA — Backup de base de datos ─────────────────────────
# Uso:
#   scripts/backup_db.sh                      # backup local de PostgreSQL
#   scripts/backup_db.sh /ruta/destino.db     # backup de SQLite
#
# En producción configurá un cron/worker que ejecute este script a diario y
# suba el archivo a un bucket (S3/R2/GCS). Ejemplo de cron diario a las 3 AM:
#   0 3 * * * /app/scripts/backup_db.sh >> /var/log/gracia-backup.log 2>&1
set -euo pipefail

STAMP=$(date +%Y%m%d_%H%M%S)
DATABASE_URL="${DATABASE_URL:-sqlite:///./gracia.db}"

if [[ "$DATABASE_URL" == postgres* ]]; then
  OUT="backups/gracia_${STAMP}.sql"
  mkdir -p backups
  echo ">>> Backing up PostgreSQL to ${OUT}"
  # Convierte postgres://user:pass@host:port/db en variables para pg_dump
  PGPASSWORD=$(echo "$DATABASE_URL" | sed -E 's#postgres(ql)?://([^:]+):([^@]+)@.*#\3#')
  HOSTPORT_DB=$(echo "$DATABASE_URL" | sed -E 's#postgres(ql)?://[^@]+@##')
  HOST=$(echo "$HOSTPORT_DB" | cut -d: -f1)
  PORT=$(echo "$HOSTPORT_DB" | sed -E 's#.*:([0-9]+)/.*#\1#')
  DB=$(echo "$HOSTPORT_DB" | sed -E 's#.*/([^/]+)$#\1#')
  USER=$(echo "$DATABASE_URL" | sed -E 's#postgres(ql)?://([^:]+):.*#\2#')

  PGPASSWORD="$PGPASSWORD" pg_dump -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -F c -f "$OUT"
  echo ">>> Backup completo: $(du -h "$OUT" | cut -f1)"
else
  DBFILE="${1:-gracia.db}"
  OUT="backups/gracia_${STAMP}.db"
  mkdir -p backups
  echo ">>> Backing up SQLite ${DBFILE} to ${OUT}"
  cp "$DBFILE" "$OUT"
  echo ">>> Backup completo: $(du -h "$OUT" | cut -f1)"
fi

# Retención: borrar backups de más de 14 días
find backups -name "gracia_*" -mtime +14 -delete
echo ">>> Listo. Últimos backups:"
ls -lht backups | head -6
