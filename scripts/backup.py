#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Backup Automatizado para Incoespacio ERP (Odoo 17)
Realiza un volcado completo de la base de datos PostgreSQL 16 y comprime el filestore.
Guarda la copia en la carpeta local 'backups/' y la replica automáticamente en Amazon S3.
"""

import os
import sys
import subprocess
import shutil
import zipfile
from datetime import datetime

# 1. Cargar variables de entorno desde .env si existe
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_FILE = os.path.join(BASE_DIR, '.env')

if os.path.isfile(ENV_FILE):
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = val

# 2. Rutas y configuración
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

DB_NAME = os.environ.get('POSTGRES_DB', 'incoespacio')
DB_USER = os.environ.get('POSTGRES_USER', 'odoo')
DB_CONTAINER = os.environ.get('DB_CONTAINER', 'incoespacio_db')
WEB_CONTAINER = os.environ.get('WEB_CONTAINER', 'incoespacio_web')

AWS_BUCKET = os.environ.get('S3_BUCKET_NAME', 'incoespacioerp-backup')
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-south-2')
AWS_KEY = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET = os.environ.get('AWS_SECRET_ACCESS_KEY')

# Formato de archivo estándar corporativo (idéntico a Incoluz e Incomueble)
TIMESTAMP = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
ARCHIVE_NAME = f"{TIMESTAMP}_incoespacioerp.zip"
FINAL_ZIP = os.path.join(BACKUP_DIR, ARCHIVE_NAME)
TEMP_DIR = os.path.join(BACKUP_DIR, f"temp_{TIMESTAMP}")

print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando backup de Incoespacio ERP (Base de Datos: {DB_NAME})...")

try:
    os.makedirs(TEMP_DIR, exist_ok=True)
    dump_sql_path = os.path.join(TEMP_DIR, 'dump.sql')

    # A. Volcado binario de PostgreSQL desde el contenedor db
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Extrayendo volcado de PostgreSQL 16 desde {DB_CONTAINER}...")
    cmd_dump = f'docker exec {DB_CONTAINER} pg_dump -U {DB_USER} -d {DB_NAME} -F c -b'
    with open(dump_sql_path, 'wb') as f:
        res = subprocess.run(cmd_dump, shell=True, stdout=f, stderr=subprocess.PIPE)
        if res.returncode != 0:
            error_msg = res.stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f"Error en pg_dump: {error_msg}")

    # B. Extracción del filestore de adjuntos desde el contenedor web
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Extrayendo filestore de Odoo 17 desde {WEB_CONTAINER}...")
    filestore_temp = os.path.join(TEMP_DIR, 'filestore')
    os.makedirs(filestore_temp, exist_ok=True)
    cmd_filestore = f'docker cp {WEB_CONTAINER}:/var/lib/odoo/filestore/{DB_NAME} "{filestore_temp}"'
    subprocess.run(cmd_filestore, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # C. Creación del archivo comprimido final ZIP
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Comprimiendo archivo final: {ARCHIVE_NAME}...")
    with zipfile.ZipFile(FINAL_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(dump_sql_path):
            zf.write(dump_sql_path, arcname='dump.sql')
        for root, dirs, files in os.walk(filestore_temp):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, TEMP_DIR)
                zf.write(full_path, arcname=rel_path)

    size_mb = os.path.getsize(FINAL_ZIP) / (1024 * 1024)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Backup local generado exitosamente: {FINAL_ZIP} ({size_mb:.2f} MB)")

    # D. Subida automática a Amazon S3
    if AWS_BUCKET and AWS_KEY and AWS_SECRET:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Replicando copia en Amazon S3 (s3://{AWS_BUCKET}/ en {AWS_REGION})...")
        try:
            import boto3
            s3_client = boto3.client(
                's3',
                region_name=AWS_REGION,
                aws_access_key_id=AWS_KEY,
                aws_secret_access_key=AWS_SECRET
            )
            s3_client.upload_file(FINAL_ZIP, AWS_BUCKET, ARCHIVE_NAME)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] OK: Copia subida correctamente a Amazon S3.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error al subir a S3 con Boto3: {e}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Intentando fallback mediante AWS CLI...")
            res_aws = subprocess.run(f'aws s3 cp "{FINAL_ZIP}" "s3://{AWS_BUCKET}/{ARCHIVE_NAME}"', shell=True)
            if res_aws.returncode == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] OK: Subida completada vía AWS CLI.")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] AVISO: No se pudo subir a S3. Compruebe credenciales.")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] AWS S3 no configurado en .env. Copia almacenada únicamente en local.")

    # E. Purga de copias locales antiguas (más de 7 días)
    retention_days = 7
    now = datetime.now().timestamp()
    for fname in os.listdir(BACKUP_DIR):
        if fname.endswith('.zip') and ('incoespacio' in fname):
            fpath = os.path.join(BACKUP_DIR, fname)
            if os.path.isfile(fpath):
                if (now - os.path.getmtime(fpath)) > (retention_days * 86400):
                    os.remove(fpath)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Purga de seguridad: Eliminada copia local antigua {fname}")

finally:
    # F. Limpieza de directorio temporal
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

print(f"[{datetime.now().strftime('%H:%M:%S')}] Proceso de backup finalizado con éxito.")
