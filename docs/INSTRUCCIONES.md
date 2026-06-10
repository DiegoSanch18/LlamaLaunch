# Guía de Puesta en Marcha: Infraestructura de IA Local 🚀

Esta guía te guiará paso a paso para completar la descarga y configuración de tu entorno de Inteligencia Artificial local utilizando la estructura de carpetas creada.

---

## 📁 Estructura del Entorno y Binarios Detectados

Tu espacio de trabajo en `C:\temp\AI Local\` está estructurado de la siguiente forma:

- 📂 `bin/llama.cpp/` ➡️ Contiene las versiones descargadas:
  - 📂 `llama-b9283-bin-win-cpu-x64/` ➡️ **Versión CPU limpia** (lista para tu notebook).
  - 📂 `cudart-llama-bin-win-cuda-13.1-x64/` ➡️ **Librerías runtime de NVIDIA CUDA** (DLLs necesarias para la aceleración por GPU).
- 📂 `models/` ➡️ Carpeta para colocar tus modelos `.gguf` descargados.
  - 📂 `edge/` ➡️ Modelos súper ligeros para notebooks (ej. Gemma-2B, Llama-3.2-3B). **¡Aquí haremos las pruebas rápidas!**
  - 📂 `chat/` ➡️ Modelos conversacionales medianos (ej. Llama-3-8B, Qwen-2.5-7B) [ideales para tu PC principal].
  - 📂 `code/` ➡️ Modelos para programar (ej. Qwen-2.5-Coder).
- 📂 `services/` ➡️ Espacio para aplicaciones y agentes locales:
  - 📂 `open-webui/` ➡️ Interfaz web estilo ChatGPT en Docker.
  - 📂 `openclaw/` ➡️ Archivos de configuración para el bot de Telegram.
  - 📂 `opencode/` ➡️ Configuraciones locales para el agente de programación.
- 📂 `scripts/` ➡️ Scripts de control y arranque:
  - ⚙️ `start-llama.bat` ➡️ **Lanzador unificado** interactivo para CPU, CUDA (NVIDIA) o Vulkan (AMD/Intel/Nvidia).
  - 🐚 `setup-openclaw.sh` ➡️ Script de WSL para instalar e iniciar OpenClaw en segundo plano.
  - 🐚 `setup-opencode.sh` ➡️ Script de WSL para instalar e iniciar el agente de código OpenCode.

> [!NOTE]
> **Compatibilidad de Rutas**: Todos los scripts de arranque (`.bat` de Windows y `.sh` de WSL) están diseñados utilizando rutas dinámicas relativas. Funcionarán perfectamente sin necesidad de modificarse en tu nueva ubicación.

---

## 1️⃣ Paso 1: Configurar llama.cpp en cada Dispositivo

### En tu Notebook (Solo CPU):
1. **Ya lo tienes todo listo.** La carpeta `llama-b9283-bin-win-cpu-x64` ya contiene todos los archivos necesarios.
2. Para arrancar la inferencia, usarás el nuevo script unificado **`scripts\start-llama.bat`** seleccionando la **Opción 1 (Solo CPU)**.

### En tu PC Principal (NVIDIA GPU - Aceleración CUDA):
La versión CUDA requiere que coloques los ejecutables de inferencia y las librerías runtime en la misma carpeta:
1. Descarga el paquete de ejecutables CUDA correspondiente en **[llama.cpp Releases en GitHub](https://github.com/ggerganov/llama.cpp/releases)**. 
2. Crea una carpeta llamada:
   `C:\temp\AI Local\bin\llama.cpp\llama-b9283-bin-win-cuda-x64\`
3. **Extrae** los ejecutables descargados dentro de esa nueva carpeta.
4. Ejecuta el script unificado **`scripts\start-llama.bat`** seleccionando la **Opción 2 (NVIDIA GPU CUDA)**.
5. 💡 **Automatización de DLLs**: La primera vez que lo abras en modo CUDA, el script detectará si te faltan las DLLs esenciales de CUDA y te ofrecerá **copiarlas automáticamente** desde tu carpeta `cudart-llama-bin-win-cuda-13.1-x64` con solo presionar un botón.

### En tu PC con Aceleración Vulkan (AMD / Intel / Nvidia Genérico):
1. Descarga el paquete de compilación Vulkan en GitHub (ej. `llama-b9283-bin-win-vulkan-x64.zip`).
2. Crea una carpeta llamada:
   `C:\temp\AI Local\bin\llama.cpp\llama-b9283-bin-win-vulkan-x64\`
3. **Extrae** los archivos allí. El script unificado **`scripts\start-llama.bat`** (Opción 3) detectará esta carpeta y ejecutará la inferencia mediante Vulkan.

---

## 2️⃣ Paso 2: Descargar los Modelos GGUF

### Para tu Notebook (Modelos Edge - Rápidos y ligeros):
Para tu notebook con **16 GB de RAM**, usaremos modelos pequeños ("Edge") que caben de sobra y responden a una velocidad increíble por CPU.

1. Abre este enlace: **[Gemma 2 2B Instruct (Bartowski en HuggingFace)](https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/tree/main)**.
2. Descarga el archivo: `gemma-2-2b-it-Q5_K_M.gguf` (~1.9 GB).
3. Guárdalo directamente en la carpeta:
   `C:\temp\AI Local\models\edge\`

### Para tu PC Principal (Modelos Chat/Code - Potentes y completos):
Para tu PC principal con **32 GB de RAM y GPU NVIDIA**, puedes utilizar modelos mucho más inteligentes.

1. Abre este enlace: **[Llama 3 8B Instruct (Bartowski en HuggingFace)](https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/tree/main)**.
2. Descarga el archivo: `Meta-Llama-3-8B-Instruct-Q5_K_M.gguf` (~5.7 GB).
3. Guárdalo en la carpeta:
   `C:\temp\AI Local\models\chat\`

*(Opcional - Para programación)*: Puedes descargar **[Qwen 2.5 Coder 7B GGUF](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/tree/main)** y colocarlo en `models/code/` para usarlo con OpenCode.

---

## 3️⃣ Paso 3: Arrancar el Servidor Unificado

El lanzador maestro ha sido migrado a una robusta e interactiva interfaz en **Python** (requiere tener instalado **Python 3.8+** en Windows). Ahora no solo inicia la inferencia, sino que incluye un **gestor de descargas de modelos automatizado (estilo `ollama pull`)**.

1. Ve a la carpeta `C:\temp\AI Local\scripts\`.
2. Haz doble clic en el script **`start-llama.bat`** (se encargará de verificar Python y arrancar el backend en segundo plano).
3. **Flujo del Gestor Interactivo (en español):**
   * **Menú Principal de Motores:** Elige tu motor de aceleración (1 para CPU, 2 para NVIDIA CUDA, 3 para Vulkan).
   * **Gestión de Modelos:** Elige la categoría de tu modelo (`edge`, `chat`, `code`).
     * *Descarga en 1 clic (Ollama Pull style)*: Si no tienes ningún modelo en esa carpeta, el lanzador te ofrecerá la opción **4** para abrir nuestra biblioteca y **descargar automáticamente modelos recomendados** (como Gemma 4 E2B o Qwen 2.5 Coder 3B/7B) directamente de Hugging Face con una barra de progreso en tiempo real.
   * **Configuración del Servidor:** El script te optimizará automáticamente los hilos de CPU y el contexto. Solo pulsa ENTER para aceptar los valores recomendados.
   * **Compresión KV (PolarQuant):** Elige habilitar PolarQuant (Opción 1 o 2) para comprimir el caché de atención y liberar hasta un 75% de VRAM y RAM, impidiendo cuelgues del sistema.
4. El servidor se iniciará automáticamente y escuchará en `http://0.0.0.0:8080`.
   ⚠️ **¡No cierres la ventana de consola negra mientras quieras usar la IA!**
   *💡 Además, el sistema de ciclo de vida del servidor (Hot-Swapping) cerrará limpiamente cualquier servidor "zombie" anterior en segundo plano para asegurar que tu GPU esté siempre libre de fugas de memoria.*

---


## 4️⃣ Paso 4: Levantar Open WebUI en Docker

Con tu servidor de inferencia ya corriendo en la consola, levantaremos la interfaz web en cualquiera de los dos equipos usando Docker.

1. Abre tu terminal (PowerShell, WSL o CMD).
2. Navega a la carpeta de configuración de Open WebUI:
   ```bash
   cd "C:\temp\AI Local\services\open-webui"
   ```
3. Ejecuta el comando para iniciar el contenedor:
   ```bash
   docker compose up -d
   ```
4. Abre tu navegador web favorito y entra en:
   **[http://localhost:3000](http://localhost:3000)**

---

## 5️⃣ Paso 5: Conectar Open WebUI con tu Inferencia Local

Al entrar por primera vez a Open WebUI:

1. **Crea una cuenta local**: Haz clic en registrarse y crea un correo y contraseña de administrador local.
2. Una vez en el panel principal:
   - Ve a la esquina inferior izquierda ➡️ **Admin Settings** (Panel de administración).
   - Ve a la pestaña **Connections** (Conexiones).
   - En la sección **OpenAI API**, haz clic en el icono de lápiz para editar o el botón `+` para añadir una conexión.
   - Introduce la siguiente URL (que apunta a tu Windows Host desde dentro de Docker):
     ```text
     http://host.docker.internal:8080/v1
     ```
   - En el campo de API Key (si lo requiere), pon cualquier palabra aleatoria (ej. `local`).
   - Haz clic en el botón **Verify / Save** (Guardar y verificar). Debería aparecer una marca de verificación verde.
3. Cierra el panel de configuración, ve al menú desplegable de modelos arriba en la pantalla principal de chat, **selecciona tu modelo Gemma o Llama** ¡y empieza a chatear!

---

## 6️⃣ Paso 6: Configurar Agentes Autónomos (OpenClaw y OpenCode) en WSL

Debido a que estas herramientas de agentes inteligentes requieren entornos Linux nativos y automatizaciones de terminal, **los ejecutaremos dentro de WSL (Ubuntu)**. 

Ambos scripts de instalación están preparados para automatizar todas las dependencias y configurar **puertas de seguridad de confirmación obligatoria** para que ningún agente realice cambios destructivos sin tu consentimiento en pantalla.

---

### 🛠️ Guía Manual: ¿Cómo instalar Node.js en WSL/Ubuntu?
Aunque el script de instalación `setup-openclaw.sh` lo hace por ti de forma automática si detecta que te falta, aquí tienes los pasos manuales detallados para que los conozcas paso a paso:

1. **Comprobar si ya tienes Node.js**:
   Abre la terminal de Ubuntu en WSL y escribe:
   ```bash
   node -v
   ```
   Si te arroja un número de versión mayor o igual a `v22.0.0`, ya estás listo. Si dice "command not found" o es una versión muy antigua, sigue los siguientes pasos.

2. **Instalar NVM (Node Version Manager)**:
   NVM es la herramienta recomendada para instalar y gestionar versiones de Node.js en Linux de forma limpia. Corre el instalador:
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
   ```

3. **Activar NVM en la consola**:
   Para empezar a usarlo inmediatamente sin tener que reiniciar la terminal, ejecuta:
   ```bash
   export NVM_DIR="$HOME/.nvm"
   [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
   ```

4. **Instalar Node.js v22 (LTS)**:
   Instala y activa la versión estable recomendada ejecutando:
   ```bash
   nvm install 22
   nvm use 22
   nvm alias default 22
   ```
   *¡Listo! Ahora al escribir `node -v` y `npm -v` verás que ya están correctamente instalados.*

---

### 🤖 Configurando OpenClaw (Asistente en Segundo Plano vía Telegram Bot)
1. Abre tu consola de **Ubuntu en WSL**.
2. Corre el script de instalación en tu nueva ruta de C:\temp\AI Local (recuerda que en WSL los espacios y guiones en los nombres de carpeta deben escaparse con barras invertidas):
   ```bash
    bash "/mnt/c/temp/AI\ Local/scripts/setup-openclaw.sh"
   ```
3. El script verificará o instalará automáticamente Node.js v22 (usando los pasos detallados arriba) y OpenClaw CLI, y luego iniciará el asistente interactivo.
4. **En el Onboarding de OpenClaw**:
   - Para LLM Provider, selecciona **`OpenAI-Compatible`**.
   - Para la URL del servidor, introduce: **`http://localhost:8080/v1`** (WSL reenvía localhost directamente al puerto 8080 de Windows donde corre tu inferencia).
   - Para API Key, pon: **`local`**.
   - Para el canal de chat, selecciona **`Telegram`** y pega el token de tu bot gratuito (créalo en 1 minuto hablándole a **@BotFather** en Telegram y usando el comando `/newbot`).
5. OpenClaw se registrará como un servicio daemon en segundo plano y podrás pedirle tareas desde Telegram en tu móvil o PC.

### 💻 Configurando OpenCode (Copiloto de Código en Terminal)
1. Abre tu consola de **Ubuntu en WSL**.
2. Corre el script de instalación en tu nueva ruta de `C:\temp\AI Local`:
   ```bash
   bash "/mnt/c/temp/AI\ Local/scripts/setup-opencode.sh"
   ```
3. El script descargará la CLI de OpenCode y configurará automáticamente las variables globales en tu archivo `~/.bashrc` apuntando a tu `llama.cpp` local.
4. **Memoria de Proyecto Integrada:** OpenCode y Open WebUI consumen automáticamente el archivo `PROJECT.md` ubicado en el directorio raíz. Asegúrate de actualizar este archivo con las convenciones específicas de tu código para que la IA actúe alineada a ellas.
5. **Control de Seguridad Activo (`tool_permissions.json`):** El entorno está fortificado con una matriz de seguridad inspirada en Claude Code. Cada herramienta posee un nivel de riesgo:
   * **Lecturas y Búsquedas (`read_file`, `grep`, `glob`):** Se auto-aprueban instantáneamente.
   * **Escritura y Shell (`edit_file`, `write_file`, `bash`):** Requieren confirmación interactiva. Para comandos de shell, el agente debe explicar la acción antes de proceder.
   * **Hooks de Respaldo Automático:** Si ejecutas un comando de modificación, el sistema comprobará si tu working tree de Git tiene cambios sin guardar y ejecutará un `git stash` automático para que puedas deshacer cualquier cambio destructivo fácilmente.
6. **Para usar el asistente:** Abre cualquier terminal de WSL en la carpeta de tus códigos locales y ejecuta:
   ```bash
   opencode chat
   ```

---

## 🤖 Guía de Uso de Herramientas Avanzadas (Claude Code Adaptation)

Hemos integrado scripts de automatización de prompts y optimización de memoria para sacarle el máximo partido a tus modelos locales:

### A. Ensamblador de System Prompts Dinámicos (`assemble-prompt.py`)
Dado que los system prompts monolíticos son demasiado pesados para modelos Edge, puedes compilar un prompt altamente preciso y comprimido según el modo que necesites:
* **Uso básico (Modo Código con memoria de proyecto):**
  ```bash
  python scripts/assemble-prompt.py --mode code --memory PROJECT.md
  ```
* **Modos de ensamblador disponibles:**
  * `plan`: Optimizado para investigación, diseño de algoritmos y estimación de complejidades sin tocar código.
  * `code`: Modo de programación activa con directivas quirúrgicas y bucle de verificación agéntico.
  * `explore`: Diseñado para auditar, buscar y navegar el codebase sin modificar archivos.
* El comando volcará el system prompt completo en pantalla. Puedes redirigirlo a un archivo o copiarlo directamente para pegarlo como un **Model Preset** en Open WebUI.

### B. Ejecución del Compactador de Contexto (`context-compactor.py`)
Si tus sesiones de chat se vuelven muy largas (>20 mensajes) y notas que tu modelo local empieza a "perder la memoria" o a fallar por falta de VRAM/RAM, puedes compactar el contexto de la conversación aplicando nuestro limpiador de 3 capas:
```bash
python scripts/context-compactor.py --input path/to/chat_history.json --budget 6000 --stats
```
*Este comando limpiará los logs redundantes de terminal, colapsará base64, aplicará un sliding window inteligente a la conversación y generará un resumen estructurado del historial antiguo a través de tu API local.*

---

## 🛑 Cómo Apagar Todo

- **Llama.cpp**: Simplemente cierra la ventana de comandos de Windows (el script `.bat` de CPU o CUDA) o presiona `Ctrl+C`.
- **Open WebUI**:
  1. En tu terminal de Docker, ve a la carpeta `services/open-webui`.
  2. Ejecuta `docker compose down` para detener el contenedor limpiamente y liberar recursos de tu PC.
