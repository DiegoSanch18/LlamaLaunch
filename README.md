# LlamaLaunch 🦙🚀

LlamaLaunch is a Desktop Inference Suite providing a clean graphical interface (GUI) and orchestrated runtime management to configure, edit startup scripts (`.bat`), and run local Large Language Models (LLMs) via `llama.cpp`.

---

## 🌟 Key Features

- **Local & Offline Inference**: Execute GGUF models directly on your hardware without telemetry or external cloud dependencies.
- **Hardware Acceleration Autodetection**: Automatically detects CPU capabilities, NVIDIA GPUs (CUDA 13.x with Flash Attention), and AMD/Intel GPUs (Vulkan), tuning threads, batch sizes, and offloading (`-ngl`).
- **Batch Script Runner & Editor**:
  - Automatically scans model directories (`G:\My Drive\AI Local\models` or fallback) to discover `.bat` scripts.
  - Interactive parameter editor and raw script viewer.
  - Safe modifications with automatic backup generation (`.bat.bak`).
- **Specialized Binary Resolution**: Dedicated priority resolver matching models to specific `llama.cpp` builds (such as dedicated ternary builds for Bonsai 2, CUDA b9297, Vulkan, or CPU).
- **Process Lifecycle & Telemetry**:
  - Background subprocess supervisor (`Popen`) with process group isolation.
  - Real-time output streaming to `active_server.log`.
  - Non-blocking `/health` polling and zombie-process termination (`kill_all_zombies`).
- **Model Downloader**: Search and download GGUF models and vision projectors (`mmproj`) directly from the Hugging Face Hub.
- **Docker & TrueNAS Scale Support**: Containerized headless deployment using KasmVNC/WebTop accessible directly through modern web browsers.

---

## 🖥️ System Requirements & Supported Environments

### Operating Systems
- **Windows 10 / 11 (64-bit)** (Native desktop experience via `pywebview` / Edge WebView2)
- **Linux / Docker** (Headless server mode with WebTop)

### Python Environment
- Python 3.10+
- Dependencies:
  ```bash
  pip install pywebview requests psutil
  ```

### Binaries (`llama.cpp`)
Binaries can be placed in `llamaLauncher/bin/llama.cpp/` or linked dynamically:
- `llama-b9297-bin-win-cuda-x64` (NVIDIA CUDA 13.x)
- `llama-b9297-bin-win-vulkan-x64` (Vulkan)
- `llama-b9283-bin-win-cpu-x64` (CPU AVX2)
- `cudart-llama-bin-win-cuda-13.1-x64` (CUDA runtime DLLs: `cublas64_*.dll`, `cublasLt64_*.dll`)

---

## 🚀 How to Use the Application

### 1. Launching LlamaLaunch

#### Native Desktop Mode (Windows)
```powershell
python llamaLauncher/app.py
```
This opens the native desktop application window running the Slate Cyberpunk dark UI.

#### Docker Decoupled Mode (Frontend :3000, Backend :5000, Gateway :8081)
The suite supports fully decoupled containerized deployment with Nginx frontend and Python backend microservices:

```powershell
# Usando el script automatizado (verifica montura G:\ y red Atomic AI):
.\run-docker.ps1

# O mediante Docker Compose directamente:
docker compose up -d --build
```

- **Frontend Web UI (`:3000`)**: `http://localhost:3000` (Interfaz web completa servida por Nginx con proxy reverso transparente a `/api/`).
- **Backend API (`:5000`)**: `http://localhost:5000/api/health` (Microservicio Python con RPC `/api/call` y escaneo de modelos).
- **Inference Gateway (`:8081`)**: `http://localhost:8081/v1/models` (Enrutador OpenAI-compatible para Atomic AI y clientes externos).
- **Modelos Vinculados**: Montura directa desde `G:\My Drive\AI Local\models` hacia `/app/models`.
- **Integración Cognitiva**: Conectado a la red Docker `atomic_ai_ai-network` para comunicación directa con el proxy de tareas atómicas.

---

### 2. Exploring Models & Batch Scripts
1. Navigate to the **Model Explorer / Manager** tab.
2. The scanner inspects your local models directory (e.g., `G:\My Drive\AI Local\models`).
3. Each model card displays:
   - **Family & Variant** tags.
   - Available **Weights (`.gguf`)**, multimodal projectors (`mmproj`), and speculative draft models (`mtp`).
   - Detected execution engine (`CUDA`, `Vulkan`, or dedicated engine such as `Bonsai 2`).
   - Available startup scripts (`run-<model>.bat`).

---

### 3. Launching & Supervising an Inference Server
1. Select the desired model and startup script from the dropdown or model card.
2. Click **Start / Launch Server**:
   - The application spawns the server as an isolated subprocess group.
   - Server status transitions: `STOPPED` ➔ `LOADING` (allocating VRAM/RAM) ➔ `RUNNING`.
   - Real-time server output is streamed to the live log viewer in the UI.
3. When `RUNNING`:
   - Click **Open Web UI** to interact with the model via `llama.cpp`'s built-in web interface (`http://localhost:8080`).
   - Use the OpenAI-compatible endpoint at `http://localhost:8080/v1` in external apps (Open-WebUI, TypingMind, VS Code extensions, etc.).
4. To stop the server cleanly or free VRAM, click **Stop Server** or **Kill Zombies**.

---

### 4. Editing `.bat` Startup Scripts
1. Select a script and open the **Batch Editor**:
   - **Form Mode (Safe)**: Tweak key hyperparameters safely (Context Size, GPU Layers `-ngl`, Threads `-t`, Port, Flash Attention `-fa`, PolarQuant KV Cache `--cache-type-k/v`).
   - **Raw Code Mode**: Direct code editor for custom flags or complex script structures.
2. Click **Save**:
   - A backup file `<script_name>.bat.bak` is automatically created.
   - Script changes are saved in UTF-8 / Windows-1252 with CRLF line endings.

---

### 5. Downloading New Models
1. Navigate to the **Downloader** tab.
2. Search Hugging Face repositories for GGUF models.
3. Select your desired quantization (e.g., `Q4_K_M`, `IQ3_S`, `Q8_0`) and vision projector (`mmproj`) if applicable.
4. Monitor streaming download progress directly within the UI.

---

### 6. Integración con Clientes Externos (OpenCode, OpenClaw, Hermes, Cursor, etc.)

Cualquier cliente o IDE compatible con el protocolo OpenAI puede consumir la suite local. Existen dos vías principales de consumo según el tipo de tarea:

| Vía de Conexión | Base URL a Configurar | Puerto Host | Descripción y Comportamiento |
| :--- | :--- | :--- | :--- |
| **Vía Cognitiva (Atomic AI)** | `http://localhost:8005/v1` | `:8005` | **Recomendada para agentes y programación**. Descompone la meta en pasos atómicos mediante micro-prompts SLM antes de ejecutar la inferencia. |
| **Vía Gateway Central (LlamaLaunch)** | `http://localhost:8081/v1` | `:8081` | **Inferencia directa en bruto**. Enruta las peticiones de forma centralizada hacia el `llama-server` activo sin descomposición. |
| **Vía Motor Físico** | `http://localhost:8080/v1` | `:8080` | Conexión directa al socket nativo de `llama-server`. |

#### Auto-Detección Dinámica de Modelo (`default` o `auto`)
No es necesario reconfigurar tus aplicaciones cada vez que cambias de modelo en LlamaLaunch:
1. En el campo **Model Name** de tu app cliente, ingresa `default`, `auto` o `auto-detect`.
2. Atomic AI y el Gateway consultan dinámicamente `/v1/models` y asumen el modelo que esté activo en memoria en ese instante.

#### Plantilla de Configuración Universal
- **Provider Type**: `OpenAI Compatible`
- **Base URL**: `http://localhost:8005/v1` *(con Atomic AI)* o `http://localhost:8081/v1` *(directo)*
- **API Key**: `llamalaunch` *(o cualquier cadena de texto)*
- **Model Name**: `default`
- **Streaming (SSE)**: `Enabled / Activado`

---

## 🧪 Running Automated Tests

To run the unit test suite verifying backend models, binaries, and API bridges:

```powershell
python -m unittest llamaLauncher/testLauncher.py -v
```

---

## 📂 Architecture Overview

```text
LlamaLaunch/
├── AGENTS.md                  # Agent governance & operational guide
├── DESIGN.md                  # UX/UI, API design & backend testing specification
├── README.md                  # Project documentation & usage guide
├── Dockerfile.frontend        # Decoupled Nginx frontend image (:3000)
├── Dockerfile.backend         # Decoupled Python backend API image (:5000)
├── Dockerfile.gateway         # Decoupled OpenAI Inference Gateway image (:8081)
├── docker-compose.yml         # Container orchestration across 3 tiers & networks
├── run-docker.ps1             # Automated PowerShell deployment script
├── run-docker.bat             # Automated Windows Batch deployment script
└── llamaLauncher/
    ├── app.py                 # Desktop application entrypoint (pywebview)
    ├── backend_server.py      # Standalone HTTP backend service (:5000)
    ├── server.py              # Legacy web server entrypoint
    ├── testLauncher.py        # Automated test suite (63 unit tests)
    ├── app/
    │   ├── backend/           # Core Python backend modules
    │   │   ├── api.py         # ApiBridge (JS-Python facade & RPC)
    │   │   ├── gateway.py     # InferenceGateway OpenAI-compatible router
    │   │   ├── batch_manager.py # .bat script parsing, template generation & backups
    │   │   ├── binaries.py    # Priority resolver for dedicated & generic llama-server binaries
    │   │   ├── config.py      # Offload & PolarQuant KV cache profiles
    │   │   ├── hardware.py    # Hardware detection & CUDA runtime DLL management
    │   │   ├── manager.py     # ProcessManager & download manager
    │   │   └── models.py      # Hierarchical model & batch script scanner
    │   └── frontend/          # Webview UI (HTML5, CSS3, Vanilla JS)
    │       ├── index.html     # Semantic dashboard markup with pipeline indicators
    │       ├── style.css      # Slate Cyberpunk dark styling
    │       ├── main.js        # Webview lifecycle & pipeline connectivity coordinator
    │       ├── manager.js     # Server controls & batch orchestration
    │       └── downloader.js  # Hugging Face downloader UI
    └── bin/llama.cpp/         # Precompiled llama.cpp binaries
```