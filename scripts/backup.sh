#!/bin/bash
# ==============================================================================
# SCRIPT DE BACKUP AUTOMATIZADO - INCOESPACIO ERP (Odoo 17)
# Volcado PostgreSQL 16 + Filestore de adjuntos Odoo
# Replicación automática en Amazon S3 (eu-south-2) y retención local de 7 días
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# 1. Cargar variables desde .env si existe
if [ -f "$BASE_DIR/.env" ]; then
    export $(grep -v '^#' "$BASE_DIR/.env" | xargs)
fi

TIMESTAMP=$(date +"%Y_%m_%d_%H_%M_%S")
BACKUP_DIR="${BASE_DIR}/backups"
DB_NAME="${POSTGRES_DB:-incoespacio}"
DB_USER="${POSTGRES_USER:-odoo}"
DB_CONTAINER="${DB_CONTAINER:-incoespacio_db}"
WEB_CONTAINER="${WEB_CONTAINER:-incoespacio_web}"
S3_BUCKET="${S3_BUCKET_NAME:-incoespacioerp-backup}"
AWS_REGION="${AWS_DEFAULT_REGION:-eu-south-2}"
RETENTION_DAYS=7

WORK_DIR="/tmp/backup_${TIMESTAMP}"
mkdir -p "${WORK_DIR}"
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Iniciando copia de seguridad de Incoespacio ERP (${DB_NAME})..."

# 2. Volcado binario PostgreSQL desde el contenedor db
echo "[$(date)] Extrayendo volcado de base de datos desde ${DB_CONTAINER}..."
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c -b > "${WORK_DIR}/dump.sql"

# 3. Copia del filestore de adjuntos desde el contenedor web
echo "[$(date)] Extrayendo filestore de adjuntos desde ${WEB_CONTAINER}..."
docker cp "${WEB_CONTAINER}:/var/lib/odoo/filestore/${DB_NAME}" "${WORK_DIR}/filestore" 2>/dev/null || mkdir -p "${WORK_DIR}/filestore"

# 4. Creación del archivo comprimido final
FINAL_ARCHIVE="${BACKUP_DIR}/${TIMESTAMP}_incoespacioerp.zip"
ARCHIVE_NAME="${TIMESTAMP}_incoespacioerp.zip"
echo "[$(date)] Empaquetando copia final: ${ARCHIVE_NAME}..."
cd "${WORK_DIR}"
zip -rq "${FINAL_ARCHIVE}" dump.sql filestore/
cd - > /dev/null

# Limpieza del directorio temporal
rm -rf "${WORK_DIR}"

echo "[$(date)] OK: Backup local generado exitosamente: ${FINAL_ARCHIVE} ($(du -h "${FINAL_ARCHIVE}" | cut -f1))"

# 5. Replicación en Amazon S3
if [ -n "${AWS_ACCESS_KEY_ID}" ] && [ -n "${AWS_SECRET_ACCESS_KEY}" ] && [ -n "${S3_BUCKET}" ]; then
    echo "[$(date)] Subiendo copia a Amazon S3 (s3://${S3_BUCKET}/ en ${AWS_REGION})..."
    if command -v aws >/dev/null 2>&1; then
        aws s3 cp "${FINAL_ARCHIVE}" "s3://${S3_BUCKET}/${ARCHIVE_NAME}" --region "${AWS_REGION}"
        echo "[$(date)] OK: Copia replicada exitosamente en S3."
    else
        # Fallback a script python con boto3
        python3 "${SCRIPT_DIR}/backup.py"
    fi
else
    echo "[$(date)] AVISO: AWS S3 no configurado en .env. Copia conservada exclusivamente en local."
fi

# 6. Purga de copias locales que superen los 7 días
find "${BACKUP_DIR}" -name "*incoespacio*.zip" -type f -mtime +${RETENTION_DAYS} -delete
echo "[$(date)] Proceso de backup finalizado."
