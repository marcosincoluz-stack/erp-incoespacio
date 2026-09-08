#!/bin/bash
# ==============================================================================
# SCRIPT DE RESTAURACIÓN Y DISASTER RECOVERY - INCOESPACIO ERP (Odoo 17)
# Uso: ./scripts/restore.sh [ruta_al_backup.zip]
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$BASE_DIR/.env" ]; then
    export $(grep -v '^#' "$BASE_DIR/.env" | xargs)
fi

DB_NAME="${POSTGRES_DB:-incoespacio}"
DB_USER="${POSTGRES_USER:-odoo}"
DB_CONTAINER="${DB_CONTAINER:-incoespacio_db}"
WEB_CONTAINER="${WEB_CONTAINER:-incoespacio_web}"
BACKUP_DIR="${BASE_DIR}/backups"

# Determinar archivo a restaurar
if [ -n "$1" ]; then
    ZIP_PATH="$1"
else
    ZIP_PATH=$(ls -t "${BACKUP_DIR}"/*.zip 2>/dev/null | head -n 1)
fi

if [ ! -f "$ZIP_PATH" ]; then
    echo "ERROR: No se encontró el archivo de backup: $ZIP_PATH"
    echo "Uso: $0 /ruta/al/backup.zip"
    exit 1
fi

echo "======================================================================"
echo "INICIANDO RESTAURACIÓN DE DESASTRE — INCOESPACIO ERP"
echo "Archivo origen: ${ZIP_PATH}"
echo "Base de datos : ${DB_NAME}"
echo "======================================================================"

TEMP_DIR="/tmp/restore_$(date +%s)"
mkdir -p "${TEMP_DIR}"

# 1. Descomprimir
echo "[1/5] Descomprimiendo archivo de backup..."
unzip -q "${ZIP_PATH}" -d "${TEMP_DIR}"

if [ ! -f "${TEMP_DIR}/dump.sql" ]; then
    echo "ERROR: El archivo no contiene dump.sql"
    rm -rf "${TEMP_DIR}"
    exit 1
fi

# 2. Detener web
echo "[2/5] Deteniendo aplicativo web temporalmente..."
docker stop "${WEB_CONTAINER}"

# 3. Terminar conexiones y recrear base de datos
echo "[3/5] Recreando base de datos en PostgreSQL 16..."
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${DB_NAME} WITH OWNER ${DB_USER};"

# 4. Restaurar volcado
echo "[4/5] Restaurando volcado de datos..."
cat "${TEMP_DIR}/dump.sql" | docker exec -i "${DB_CONTAINER}" pg_restore -U "${DB_USER}" -d "${DB_NAME}" --no-owner || true

# 5. Restaurar filestore y arrancar web
echo "[5/5] Restaurando filestore de adjuntos..."
docker start "${WEB_CONTAINER}"

if [ -d "${TEMP_DIR}/filestore" ]; then
    if [ -d "${TEMP_DIR}/filestore/${DB_NAME}" ]; then
        docker cp "${TEMP_DIR}/filestore/${DB_NAME}/." "${WEB_CONTAINER}:/var/lib/odoo/filestore/${DB_NAME}"
    else
        docker cp "${TEMP_DIR}/filestore/." "${WEB_CONTAINER}:/var/lib/odoo/filestore/${DB_NAME}"
    fi
    docker exec -u 0 "${WEB_CONTAINER}" chown -R odoo:odoo /var/lib/odoo/filestore
fi

rm -rf "${TEMP_DIR}"

echo "======================================================================"
echo "RESTAURACIÓN COMPLETADA CON ÉXITO"
echo "======================================================================"
