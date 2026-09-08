#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Actualización Rápida de Módulos para Incoespacio ERP (Odoo 17)
Permite actualizar uno, varios o todos los módulos custom sin recrear contenedores.
Uso:
  python update_modules.py                      (actualiza todos los módulos incoespacio_*)
  python update_modules.py incoespacio_theme    (actualiza un módulo específico)
"""

import sys
import os
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_FILE = os.path.join(BASE_DIR, '.env')

DB_NAME = "incoespacio"
WEB_CONTAINER = "incoespacio_web"

if os.path.isfile(ENV_FILE):
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('POSTGRES_DB='):
                DB_NAME = line.split('=', 1)[1].strip().strip('"').strip("'")
            elif line.startswith('WEB_CONTAINER='):
                WEB_CONTAINER = line.split('=', 1)[1].strip().strip('"').strip("'")

MODULES_DEFAULT = [
    "incoespacio_security",
    "incoespacio_theme",
    "incoespacio_reports",
    "incoespacio_invoice_date",
    "incoespacio_invoice_notes",
    "incoespacio_partner_is_customer_or_supplier",
    "incoespacio_purchase_bot_alert",
    "incoespacio_support"
]

if len(sys.argv) > 1:
    modules_to_update = ",".join(sys.argv[1:])
else:
    modules_to_update = ",".join(MODULES_DEFAULT)

print("=" * 70)
print(f"ACTUALIZANDO MÓDULOS EN ODOO 17 ({DB_NAME})")
print(f"Módulos: {modules_to_update}")
print("=" * 70)

cmd = f'docker exec {WEB_CONTAINER} odoo -u {modules_to_update} -d {DB_NAME} --stop-after-init'
res = subprocess.run(cmd, shell=True)

if res.returncode == 0:
    print("\nActualización completada con éxito.")
else:
    print(f"\nError al actualizar módulos (código {res.returncode}).")
    sys.exit(res.returncode)
