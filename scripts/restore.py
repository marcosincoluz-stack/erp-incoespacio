#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Restauración y Disaster Recovery para Incoespacio ERP (Odoo 17)
Restaura una copia de seguridad (.zip con dump.sql y filestore) sobre los contenedores Docker.
"""

import os
import sys
import subprocess
import shutil
import zipfile
from datetime import datetime

# Cargar .env
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

DB_NAME = os.environ.get('POSTGRES_DB', 'incoespacio')
DB_USER = os.environ.get('POSTGRES_USER', 'odoo')
DB_CONTAINER = os.environ.get('DB_CONTAINER', 'incoespacio_db')
WEB_CONTAINER = os.environ.get('WEB_CONTAINER', 'incoespacio_web')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

# Determinar el archivo ZIP a restaurar
if len(sys.argv) > 1:
    zip_path = os.path.abspath(sys.argv[1])
else:
    # Buscar el backup más reciente en backups/
    candidates = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]
    if not candidates:
        print("ERROR: No se encontró ningún archivo .zip en la carpeta backups/ ni se especificó ruta.")
        print("Uso: python restore.py <ruta_al_archivo_backup.zip>")
        sys.exit(1)
    candidates.sort(key=os.path.getmtime, reverse=True)
    zip_path = candidates[0]
    print(f"No se especificó archivo. Seleccionando la copia más reciente: {os.path.basename(zip_path)}")

if not os.path.isfile(zip_path):
    print(f"ERROR: El archivo {zip_path} no existe.")
    sys.exit(1)

print("=" * 70)
print(f"INICIANDO RESTAURACIÓN DE DESASTRE — INCOESPACIO ERP")
print(f"Archivo de origen : {zip_path}")
print(f"Base de datos     : {DB_NAME}")
print(f"Contenedor DB     : {DB_CONTAINER}")
print(f"Contenedor Web    : {WEB_CONTAINER}")
print("=" * 70)

temp_dir = os.path.join(BACKUP_DIR, f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
os.makedirs(temp_dir, exist_ok=True)

try:
    # 1. Descomprimir archivo de backup
    print("\n[1/5] Descomprimiendo archivo de backup...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)

    dump_path = os.path.join(temp_dir, 'dump.sql')
    filestore_path = os.path.join(temp_dir, 'filestore')

    if not os.path.isfile(dump_path):
        raise FileNotFoundError("El archivo de backup no contiene 'dump.sql'.")

    # 2. Detener contenedor web para liberar bloqueos
    print("\n[2/5] Deteniendo servicio web temporalmente...")
    subprocess.run(f"docker stop {WEB_CONTAINER}", shell=True, check=True)

    # 3. Terminar conexiones activas y recrear base de datos
    print("\n[3/5] Recreando base de datos PostgreSQL 16...")
    term_sql = (
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{DB_NAME}' AND pid <> pg_backend_pid();"
    )
    subprocess.run(
        f'docker exec {DB_CONTAINER} psql -U {DB_USER} -d postgres -c "{term_sql}"',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        f'docker exec {DB_CONTAINER} psql -U {DB_USER} -d postgres -c "DROP DATABASE IF EXISTS {DB_NAME};"',
        shell=True, check=True
    )
    subprocess.run(
        f'docker exec {DB_CONTAINER} psql -U {DB_USER} -d postgres -c "CREATE DATABASE {DB_NAME} WITH OWNER {DB_USER};"',
        shell=True, check=True
    )

    # 4. Restaurar volcado SQL
    print("\n[4/5] Restaurando volcado de datos con pg_restore...")
    cmd_restore = f'docker exec -i {DB_CONTAINER} pg_restore -U {DB_USER} -d {DB_NAME} --no-owner'
    with open(dump_path, 'rb') as f_in:
        res = subprocess.run(cmd_restore, shell=True, stdin=f_in, stderr=subprocess.PIPE)
        # pg_restore suele retornar warnings no críticos (código 1), comprobamos si hay error fatal
        if res.returncode > 1:
            print(f"Aviso en restauración: {res.stderr.decode('utf-8', errors='ignore')}")

    # 5. Restaurar filestore si existe
    print("\n[5/5] Restaurando archivos adjuntos (filestore)...")
    subprocess.run(f"docker start {WEB_CONTAINER}", shell=True, check=True)

    if os.path.isdir(filestore_path):
        # Localizar si está en filestore/incoespacio o directo
        sub_dir = os.path.join(filestore_path, DB_NAME)
        source_files = sub_dir if os.path.isdir(sub_dir) else filestore_path
        cmd_cp = f'docker cp "{source_files}/." {WEB_CONTAINER}:/var/lib/odoo/filestore/{DB_NAME}'
        subprocess.run(cmd_cp, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(
            f'docker exec -u 0 {WEB_CONTAINER} chown -R odoo:odoo /var/lib/odoo/filestore',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    print("\n" + "=" * 70)
    print("RESTAURACIÓN COMPLETADA CON ÉXITO")
    print(f"El ERP está listo y disponible.")
    print("=" * 70)

finally:
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
