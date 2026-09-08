<div align="center">

# Incoespacio ERP

[![Odoo](https://img.shields.io/badge/17.0-Odoo-a24689?style=flat-square&logo=odoo)](https://www.odoo.com/)
[![PostgreSQL](https://img.shields.io/badge/16-PostgreSQL-306792?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/-Docker-0073ea?style=flat-square&logo=docker)](https://www.docker.com/)
[![Nginx](https://img.shields.io/badge/-Nginx-009639?style=flat-square&logo=nginx)](https://nginx.org/)

</div>

## Introducción

Este repositorio contiene la configuración de Docker y el código fuente para el despliegue de **Odoo 17 Community Edition** junto con los módulos custom de **Incoespacio** y las dependencias de la comunidad (OCA).

---

## Servicios y Arquitectura

| Servicio | Contenedor | Descripción | Puertos |
| :--- | :--- | :--- | :--- |
| **nginx** | `incoespacio_nginx` | Reverse proxy con SSL, compresión gzip y WebSockets | `80`, `443` |
| **web** | `incoespacio_web` | Servidor aplicativo Odoo 17 CE | `8070:8069` |
| **db** | `incoespacio_db` | Motor de base de datos PostgreSQL 16 | *(red interna)* |

---

## Volúmenes y Persistencia

- **Datos de Odoo y sesiones**: `incoespacio_web_data -> /var/lib/odoo`
- **Base de datos PostgreSQL**: `incoespacio_db_data -> /var/lib/postgresql/data/pgdata`
- **Configuración Odoo**: `./config -> /etc/odoo`
- **Módulos propios de Incoespacio**: `./addons-incoespacio -> /mnt/incoespacio-addons`
- **Módulos externos y OCA**: `./addons -> /mnt/extra-addons`
- **Proxy y certificados SSL**: `./nginx -> /etc/nginx/...`

---

## Despliegue Rápido

```bash
# 1. Copiar y configurar variables de entorno
cp .env.example .env

# 2. Configurar odoo.conf si es necesario
cp config/odoo.conf_example config/odoo.conf

# 3. Iniciar el stack completo
docker compose up -d

# 4. Ver logs en tiempo real
docker compose logs -f web
```

---

## Github Workflow

### Estructura de Ramas

- **`main`**: Rama principal, contiene la última versión estable en producción.
- **`feat-*`**: Ramas de características, para desarrollo de nuevas funcionalidades.
- **`hotfix-*`**: Correcciones urgentes de errores sobre producción.

### Commit Guidelines

Formato del mensaje de commit:
`[TAG] + nombre_del_modulo: descripcion del cambio`

* **`[ADD]`**: Para agregar nuevos módulos o características.
* **`[FIX]`**: Corrección de errores y bugs.
* **`[REF]`**: Refactorización de código existente sin alterar funcionalidad.
* **`[IMP]`**: Mejoras incrementales en rendimiento o experiencia de usuario.
* **`[DEL]`**: Eliminación de código muerto, vistas o módulos en desuso.
* **`[REV]`**: Reversión de commits anteriores.
* **`[REL]`**: Commits de lanzamiento y nuevas versiones.
* **`[MERGE]`**: Fusiones de ramas.
* **`[I18N]`**: Cambios y mejoras en archivos de traducción.
