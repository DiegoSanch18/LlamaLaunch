# AI Local — Memoria de Proyecto 🧠

> Este archivo es la "memoria persistente" del workspace. Cualquier agente o sesión de chat debe leerlo al inicio para entender el contexto del proyecto. Inspirado en el concepto `CLAUDE.md` filtrado de Claude Code.

## Arquitectura del Entorno
- **Inferencia**: llama.cpp corriendo en Windows (CPU o CUDA/Vulkan) en puerto 8080
- **Interfaz**: Open WebUI en Docker (puerto 3000), conecta vía `host.docker.internal:8080`
- **Agentes**: OpenCode y OpenClaw en WSL Ubuntu, conectan vía gateway IP dinámica
- **Modelos Edge** (Notebook 16GB): Gemma 4 E2B, Qwen 2.5 Coder 3B, Gemma 2 2B
- **Modelos PC** (32GB + GPU): Llama 3 8B, Qwen 2.5 Coder 7B

## Estructura del Directorio
El directorio raíz contiene exactamente 4 carpetas principales de código y documentación:
- **docs/**: Contiene toda la documentación del proyecto (esta memoria, planes de servicio, arquitectura, instrucciones).
- **models/**: Almacenamiento de modelos locales de lenguaje.
- **llamaLauncher/**: Código fuente de la aplicación lanzadora de llama.cpp.
- **services/**: Servicios auxiliares y contenedores (Open WebUI, base de datos, etc.).

## Convenciones de Código
- Lenguaje preferido: Python 3.10+ para scripts, Bash para WSL
- Encoding: UTF-8 sin BOM en todos los archivos
- Scripts Windows (.bat): Diseño lineal sin bloques parentizados (evitar crash de CMD)
- Documentación: Markdown con diagramas Mermaid cuando sea útil
- Idioma de documentación: Español

## Comandos Útiles
- Arrancar inferencia (Desarrollo): `python llamaLauncher/app.py`
- Compilar a Ejecutable (.exe): `python llamaLauncher/buildLauncher.py`
- Ejecutar Pruebas Unitarias: `python llamaLauncher/testLauncher.py`
- Arrancar Open WebUI: `cd services\open-webui && docker compose up -d`

## Reglas de Seguridad
- NUNCA ejecutar comandos destructivos sin confirmación explícita del usuario
- Preferir `git stash` antes de cambios grandes
- Operaciones de lectura (grep, cat, ls) son auto-aprobadas
- Operaciones de escritura/ejecución requieren confirmación Y/N

## Lecciones Aprendidas
- SQLite NO funciona sobre Google Drive/drvfs → usar Docker named volumes
- WSL 2 NAT cambia IP en cada reinicio → resolver dinámicamente con `ip route`
- CMD crashea con `::` dentro de bloques `()` → usar `rem`
- CMD crashea con emojis en variables → solo usar ASCII en lógica, emojis solo en `echo`
