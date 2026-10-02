# Reglas y Guía Operativa para Agentes — LlamaLaunch 🦙🚀

Este archivo define el protocolo de actuación obligatorio para cualquier agente de inteligencia artificial (Antigravity, Cursor, OpenCode, Claude Code, Aider, etc.) que opere dentro del repositorio **LlamaLaunch** (`C:\git\LlamaLaunch`).

---

## 1. Misión y Alcance del Repositorio

**LlamaLaunch** es una suite de escritorio (Desktop Inference Suite) basada en **Python + pywebview** (frontend HTML5/CSS3/Vanilla JS y backend modular Python) diseñada para orquestar, configurar, editar scripts de arranque (`.bat`) y supervisar servidores de inferencia local (`llama-server`) para Modelos de Lenguaje Grande (LLMs) en formato GGUF.

El repositorio interactúa estrechamente con el ecosistema **AI Local**:
- **Pesos y Scripts de Modelos:** `G:\My Drive\AI Local\models`
- **Binarios de Ejecución:** `C:\git\LlamaLaunch\llamaLauncher\bin\llama.cpp` y carpetas dedicadas por modelo (ej. `models\Bonsai 2\llama.cpp`).
- **Hardware de Ejecución:** Documentado exhaustivamente en `G:\My Drive\AI Local\HARDWARE.md`.

---

## 2. Topología de Hardware y Políticas de Recursos

> [!IMPORTANT]
> **Lectura Obligatoria de Hardware:**
> Antes de modificar parámetros de inferencia, plantillas de scripts `.bat` o configuraciones de offload, consulta [HARDWARE.md](file:///G:/My%20Drive/AI%20Local/HARDWARE.md).

Los tres nodos del ecosistema tienen restricciones estrictas:

1. **`DIEGO_DESKTOP` (Estación Principal):**
   - **CPU:** AMD Ryzen 7 5700X OC (8C/16T, 32 GB DDR4).
   - **GPU:** NVIDIA GeForce RTX 5060 Ti (16 GB VRAM dedicada GDDR7/GDDR6X).
   - **Backend:** CUDA 13.x con Flash Attention activo (`--flash-attn on`).
   - **Flags Típicos:** `-ngl 99 --flash-attn on --cache-type-k q4_0 --cache-type-v q4_0 -t 8 --ubatch-size 512`.
   - **Capacidad:** 14B a `Q8_0` / `Q5_K_M` (100% VRAM), MoE 35B (`UD-IQ3_S`) 100% VRAM, Ternary 27B (`PQ2_0`) 100% VRAM.

2. **`TRUENAS_SERVER` (Servidor 24/7):**
   - **CPU:** AMD Ryzen 3 3100 (4C/8T, 24 GB RAM).
   - **GPUs:** 2x NVIDIA GeForce GTX 1660 Super (12 GB VRAM combinada, 6 GB c/u).
   - **Backend:** CUDA con división de tensores (`--tensor-split 1,1` o `--split-mode row`). Flash Attention desactivado (`--flash-attn off`).

3. **`DIEGOLAPTOP` (Entorno Móvil):**
   - **CPU:** AMD Ryzen 7 7735U (8C/16T, 16 GB RAM unificada).
   - **GPU:** AMD Radeon 680M (Vulkan).
   - **Backend:** Compilación Vulkan (`llama-*-bin-win-vulkan-x64`). Modelos edge 2B-7B (`Gemma 4 E2B`, `Llama 3.2 3B`).

---

## 3. Estructura del Repositorio y Arquitectura

```text
C:\git\LlamaLaunch/
├── AGENTS.md                          # Este archivo de gobernanza técnica
├── DESIGN.md                          # Especificación UX/UI, Contrato API y Estrategia de Pruebas
├── README.md                          # Documentación pública y guía de instalación
├── Dockerfile                         # Contenedor Linux WebTop para TrueNAS/Headless
├── docker-compose.yml                 # Despliegue containerizado
├── llamaLauncher/
│   ├── app.py                         # Punto de entrada de escritorio (pywebview GUI)
│   ├── buildLauncher.py               # Script de compilación PyInstaller a binario standalone
│   ├── testLauncher.py                # Suite de pruebas unitarias backend
│   ├── app/
│   │   ├── backend/                   # Lógica de negocio desacoplada de la interfaz
│   │   │   ├── api.py                 # ApiBridge: Fachada de comunicación expuesta a JS
│   │   │   ├── config.py              # Perfiles de optimización y flags de PolarQuant KV
│   │   │   ├── hardware.py            # Detección no bloqueante de CPU (cores) y GPUs (CUDA/Vulkan)
│   │   │   ├── manager.py             # ProcessManager (Singleton Popen) y DownloadManager
│   │   │   └── models.py              # Escaneo de modelos locales y catálogo Hugging Face
│   │   └── frontend/                  # Interfaz gráfica webview (HTML5/CSS3/JS Vanilla)
│   │       ├── index.html             # Maquetación semántica del Dashboard y Tabs
│   │       ├── style.css              # Sistema de diseño "Slate Cyberpunk Dark Mode"
│   │       ├── main.js                # Orquestador del ciclo de vida pywebview y estado global
│   │       ├── manager.js             # Lógica del panel de control de servidor y batch runner
│   │       └── downloader.js          # Búsqueda en Hugging Face Hub y descargas en streaming
│   ├── bin/llama.cpp/                 # Binarios de inferencia precompilados
│   │   ├── llama-b9297-bin-win-cuda-x64/    # Compilación CUDA 13.x para NVIDIA
│   │   ├── llama-b9297-bin-win-vulkan-x64/  # Compilación Vulkan para AMD/Intel
│   │   ├── llama-b9283-bin-win-cpu-x64/     # Compilación CPU pura AVX2
│   │   └── cudart-llama-bin-win-cuda-13.1-x64/ # DLLs de runtime CUDA requeridas
│   └── logs/                          # Registros de ejecución y auditoría
│       ├── active_server.log          # Salida estándar y error del servidor en ejecución
│       ├── server_history.log         # Bitácora histórica cronológica de inicios
│       └── history.json               # Timestamp del último uso por modelo
```

---

## 4. Gestión de Scripts `.bat` y Motores de Inferencia

### 4.1. Filosofía de Lanzamiento: Batch Runner vs. CLI Directo
El repositorio implementa soporte dual de ejecución:
1. **Modo Directo (Legacy):** Generación dinámica de flags CLI hacia `llama-server.exe` desde los controles de la UI.
2. **Modo Batch Orquestado (Recomendado):** Descubrimiento, visualización, edición interactiva y lanzamiento directo de scripts `.bat` residentes en cada carpeta de modelo (`G:\My Drive\AI Local\models\<Modelo>\*.bat`).

### 4.2. Tratamiento de Binarios Especializados y Variantes
No todos los modelos corren sobre el mismo binario de `llama.cpp`:
- **Modelos Ternarios / 1-bit (`Bonsai 2`):**
  - Modelos como `Ternary-Bonsai-2-27B-PQ2_0.gguf` requieren una versión de `llama.cpp` compilada con kernels especializados para cuantización ternaria (`PQ2_0`, `PTQ1_0`).
  - Su binario dedicado reside en `G:\My Drive\AI Local\models\Bonsai 2\llama.cpp\llama-server.exe`.
  - El sistema **nunca** debe forzar un binario genérico sobre Bonsai 2, pues fallará al cargar el grafo de tensores.
- **Modelos Generales CUDA:**
  - Emplean `bin/llama.cpp/llama-b9297-bin-win-cuda-x64`. Requieren verificación de DLLs (`cublasLt64_*.dll`, `cublas64_*.dll`) mediante `hardware.check_and_copy_cuda_dlls()`.
- **Modelos en Vulkan:**
  - Emplean `bin/llama.cpp/llama-b9297-bin-win-vulkan-x64`. Adecuados para la GPU integrada Radeon 680M en laptops o cuando CUDA está ocupado.
- **Modelos con Multimodalidad y MTP:**
  - Modelos con proyector de visión (`--mmproj`) o decodificación especulativa MTP (`--spec-type draft-mtp`) poseen variables específicas en sus scripts `.bat` que deben preservarse en caso de edición.

### 4.3. Reglas para la Edición de `.bat`
- **Respaldo Automático:** Toda edición de un archivo `.bat` debe generar un respaldo de seguridad con sufijo `.bat.bak` antes de persistir los cambios.
- **Codificación:** Los scripts `.bat` deben leerse y guardarse estrictamente en codificación **ANSI / Windows-1252 o UTF-8 sin BOM**, preservando saltos de línea `CRLF` (`\r\n`).
- **Preservación de Variables de Entorno Dinámicas:** No reemplazar variables como `%~dp0`, `!MMPROJ_FLAG!`, `%BASEDIR%` por rutas estáticas absolutas, a fin de no romper la portabilidad si se mueve el directorio.

---

## 5. Directivas de Desarrollo, Git y Entorno

1. **Ubicación Determinista de Repositorios:**
   - Este repositorio reside en `C:\git\LlamaLaunch`. Prohibido inicializar subrepositorios o mover la carpeta git a `G:\My Drive`.
2. **Entorno Shell en Windows:**
   - La subshell de comandos es no interactiva (headless).
   - Para operaciones de red Git, utilizar siempre:
     ```powershell
     $env:GIT_TERMINAL_PROMPT = '0'
     $env:GCM_INTERACTIVE = 'never'
     ```
3. **Nomenclatura de Ramas Git:**
   - Seguir estrictamente el estándar:
     - `feat/<numero>-<descripcionCortaCamelCase>` (ej. `feat/301-editorBatInteractivo`)
     - `bug/<numero>-<descripcionCortaCamelCase>` (ej. `bug/302-fixDeteccionBinarioBonsai`)
4. **Pruebas y Verificación:**
   - Cualquier cambio en la lógica de backend debe acompañarse de pruebas automatizadas en `llamaLauncher/testLauncher.py` (o módulos satélites en tests/).
   - Ejecutar la suite antes de dar por cerrada una tarea:
     ```cmd
     python -m unittest llamaLauncher/testLauncher.py -v
     ```
5. **No Inventar Dependencias:**
   - Mantener el footprint mínimo: dependencias permitidas en backend son `pywebview`, `requests`, `psutil`. No introducir frameworks pesados adicionales sin justificación explícita.
