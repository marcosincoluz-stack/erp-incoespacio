#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualiza módulos de addons-incoespacio sin recrear contenedores.

  python scripts/update_modules.py
  python scripts/update_modules.py incoespacio_theme otro_modulo
"""
import os
import subprocess
import sys

from custom_modules import custom_modules

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_FILE = os.path.join(BASE_DIR, ".env")


def _env(key, default):
    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def main():
    known = custom_modules()
    mods = sys.argv[1:] or known
    # Solo carpetas de modulo reales: los nombres van a un comando de shell.
    missing = [name for name in mods if name not in known]
    if missing:
        sys.exit("Modulo fuera de addons-incoespacio: " + ", ".join(missing))
    db = _env("POSTGRES_DB", "incoespacio")
    web = _env("WEB_CONTAINER", "incoespacio_web")
    listed = ",".join(mods)
    print(f"Actualizando en {db}: {listed}")
    # workers 0 y otro puerto: el contenedor ya tiene el Odoo de produccion en el 8069.
    cmd = (
        f"docker exec {web} odoo -u {listed} -d {db} --stop-after-init "
        "--workers=0 --max-cron-threads=0 --http-port=8098"
    )
    return subprocess.run(cmd, shell=True).returncode


if __name__ == "__main__":
    sys.exit(main())
