#!/bin/bash
# Copia Incoespacio ERP: pg_dump en el contenedor db (no en Odoo) + filestore → S3.
# En la EC2 usa el rol de instancia. No hace falta AWS_ACCESS_KEY_ID en .env.
# Cron: PATH mínimo; este script fija PATH.

set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${BASE_DIR}/.env"

env_get() {
    local key="$1"
    local default="${2:-}"
    if [ -f "$ENV_FILE" ]; then
        local val
        val="$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '\r' | sed 's/^["'\'']//;s/["'\'']$//')"
        if [ -n "$val" ]; then
            printf '%s' "$val"
            return
        fi
    fi
    printf '%s' "$default"
}

TIMESTAMP="$(date +"%Y_%m_%d_%H_%M_%S")"
BACKUP_DIR="${BASE_DIR}/backups"
# POSTGRES_DB del .env es la BD de arranque del contenedor (postgres), no la de Odoo.
DB_NAME="${ODOO_DB:-incoespacio}"
DB_USER="$(env_get POSTGRES_USER odoo)"
DB_CONTAINER="${DB_CONTAINER:-incoespacio_db}"
WEB_CONTAINER="${WEB_CONTAINER:-incoespacio_web}"
S3_BUCKET="$(env_get S3_BUCKET_NAME incoespacioerp-backup)"
AWS_REGION="$(env_get AWS_DEFAULT_REGION eu-south-2)"
S3_PREFIX="prod"
RETENTION_DAYS=7

WORK_DIR="/tmp/backup_${TIMESTAMP}"
mkdir -p "${WORK_DIR}" "${BACKUP_DIR}"

echo "[$(date)] Iniciando copia Incoespacio ERP (${DB_NAME})..."

echo "[$(date)] pg_dump desde ${DB_CONTAINER}..."
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c -b > "${WORK_DIR}/dump.sql"

echo "[$(date)] Filestore desde ${WEB_CONTAINER}..."
docker cp "${WEB_CONTAINER}:/var/lib/odoo/filestore/${DB_NAME}" "${WORK_DIR}/filestore" 2>/dev/null || mkdir -p "${WORK_DIR}/filestore"

ARCHIVE_NAME="${TIMESTAMP}_incoespacioerp.zip"
FINAL_ARCHIVE="${BACKUP_DIR}/${ARCHIVE_NAME}"
echo "[$(date)] ZIP ${ARCHIVE_NAME}..."
(
    cd "${WORK_DIR}"
    zip -rq "${FINAL_ARCHIVE}" dump.sql filestore/
)
rm -rf "${WORK_DIR}"
echo "[$(date)] OK local: ${FINAL_ARCHIVE} ($(du -h "${FINAL_ARCHIVE}" | cut -f1))"

S3_URI="s3://${S3_BUCKET}/${S3_PREFIX}/${ARCHIVE_NAME}"
echo "[$(date)] Subiendo ${S3_URI} (${AWS_REGION})..."
if ! command -v aws >/dev/null 2>&1; then
    echo "[$(date)] ERROR: aws CLI no está en PATH." >&2
    exit 1
fi
aws s3 cp "${FINAL_ARCHIVE}" "${S3_URI}" --region "${AWS_REGION}"
echo "[$(date)] OK S3."

find "${BACKUP_DIR}" -name "*incoespacio*.zip" -type f -mtime +${RETENTION_DAYS} -delete
echo "[$(date)] Backup finalizado."
