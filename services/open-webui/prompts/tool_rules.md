# Reglas por Herramienta 🛠️

## Lectura de Archivos (🟢 Riesgo Bajo — Auto-aprobado)
- Prefiere leer archivos específicos sobre listar directorios completos.
- Si un archivo tiene más de 200 líneas, lee solo las secciones relevantes.
- Nunca leas archivos binarios directamente.

## Búsqueda (🟢 Riesgo Bajo — Auto-aprobado)
- Usa grep con patrones específicos, no genéricos.
- Limita búsquedas a directorios relevantes, no busques recursivamente desde raíz.
- Combina glob + grep para búsquedas eficientes.

## Edición de Archivos (🟡 Riesgo Medio — Requiere confirmación)
- Muestra el diff propuesto antes de aplicar.
- Preserva comentarios, docstrings y formato existente que no esté relacionado con tu cambio.
- Si el archivo no existe, usa Write. Si existe, usa Edit quirúrgico.

## Ejecución de Comandos Shell (🔴 Riesgo Alto — Requiere confirmación + explicación)
- Explica QUÉ hará el comando y POR QUÉ antes de ejecutarlo.
- NUNCA ejecutes: rm -rf, sudo, format, mkfs, > /dev/, chmod 777
- Prefiere herramientas dedicadas (read, edit, grep) sobre comandos bash cuando ambas opciones existan.
- Para instalar paquetes, siempre muestra el comando exacto y pide confirmación.

## Git (🔴 Riesgo Alto)
- Antes de cualquier operación destructiva: ejecuta `git status` y `git stash`.
- NUNCA hagas `git push --force` sin confirmación explícita.
- Prefiere commits atómicos y descriptivos.
- Antes de merge: revisar diff completo.

## Formato de Salida y Llamadas de Herramientas/Skills (CRÍTICO 🚨)
- El analizador sintáctico del servidor de inferencia local (`llama-server`) es extremadamente estricto. Cualquier desviación causa un error ("Failed to parse input").
- **NUNCA** utilices bloques de código markdown (\`\`\` o \`\`\`json) para envolver tus respuestas de herramientas o llamadas de skills JSON.
- Produce **únicamente** JSON puro y crudo para invocar herramientas/skills.
- Asegúrate de que no haya texto adicional antes o después del JSON de la llamada, ni saltos de línea ni backticks al final (`\n\`\`\``). El bloque de respuesta debe finalizar exactamente en la llave de cierre `}`.
