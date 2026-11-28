# Incoespacio: Asistente con IA, catálogo

Una sola herramienta, `consultar`, para que IncoBot filtre, ordene y limite datos del ERP sin una herramienta a medida por pregunta. Plan: `docs/asistente-ia-catalogo.md`.

- **Catálogo** (`_catalog()`, cada módulo añade lo suyo): qué se puede consultar y qué significa cada campo, en español. Un campo puede pedir un grupo para verse (coste y margen piden Facturación).
- **La IA no escribe consultas de Odoo**: manda filtros (campo, operador, valor) y este código los traduce, comprobando que todo esté en el catálogo, que el operador valga para el tipo y que el valor sea del tipo bueno.
- **Seguridad**: como el usuario y sin sudo (lectura de `incoespacio_assistant_ai_data`), en solo lectura, con la lista negra como segunda barrera (`_catalog_checked`), como mucho 50 filas.
- **Agrupar y sumar** (`agrupar`, `sumar`; fechas por mes o año) con `read_group`, como mucho 30 grupos. **Campos calculados** (margen): se pueden ordenar y filtrar leyendo hasta 200 registros (`models/question_more.py`).
- Entradas hoy: `facturas`, `pagos` y `contactos` (`incoespacio_assistant_ai_invoice`); `obras`, `certificaciones`, `compras` y `proyectos` (`incoespacio_assistant_ai_construction`).
- **Test de oro** (`tests/gold.py`): cada módulo lo llama con sus usuarios de prueba; comprueba todas las entradas del catálogo.
