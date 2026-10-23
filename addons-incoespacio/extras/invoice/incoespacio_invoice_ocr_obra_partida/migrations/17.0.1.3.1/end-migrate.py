def migrate(cr, version):
    # Los asistentes viejos son transitorios. Borrar el ir.model choca con
    # el chequeo de columnas de módulo; se dejan y Odoo solo avisa al arrancar.
    return
