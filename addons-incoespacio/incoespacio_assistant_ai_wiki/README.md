# Incoespacio: Asistente con IA, wiki

IncoBot contesta las preguntas de «cómo se hace» con la wiki de uso (`docs/wiki/`).

- A Gemini solo se le manda el índice (`README.md`) y la lista de páginas. Abre la que necesita con la herramienta `wiki_pagina`, así el coste no crece con la wiki.
- Solo abre archivos `.md` de dentro de la carpeta, de la lista que se lee en cada pregunta. Se salta enlaces simbólicos, carpetas ocultas y cualquier ruta que salga de la carpeta (`..`, rutas absolutas).
- La carpeta es `/mnt/wiki` en el contenedor, montada en solo lectura: `./docs/wiki:/mnt/wiki:ro` en `docker-compose.yml`. Se puede cambiar con el parámetro del sistema `incoespacio_assistant_ai.wiki_path`; no está en Ajustes a propósito.
- Sin carpeta, IncoBot no tiene la herramienta y responde que eso aún no está en la wiki.
