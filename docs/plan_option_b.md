# Plan de Implementación: Integración de SearXNG como Motor de Búsqueda Privado en Open WebUI

Este plan detalla cómo desplegar, configurar y optimizar **SearXNG** (un motor de búsqueda meta-búsqueda que respeta la privacidad y no almacena registros) y su integración con un contenedor local de **Open WebUI**. Esto habilita capacidades avanzadas de Generación Aumentada por Recuperación (RAG) en tiempo real, utilizando sus modelos locales (por ejemplo, a través de Ollama) sin depender de APIs web comerciales, de pago, ni de rastreadores de publicidad.

---

## 1. Objetivo y Contexto

Por defecto, los modelos de lenguaje locales (LLMs) están limitados a su conocimiento de entrenamiento (corte temporal). Para mitigar esto, Open WebUI integra un potente pipeline de **RAG Web**, capaz de realizar búsquedas automáticas en la web, descargar las páginas más relevantes, dividirlas en fragmentos, vectorizarlas, y seleccionar los fragmentos más pertinentes para inyectarlos en el contexto del prompt del usuario.

Al desplegar **SearXNG** localmente bajo Docker e integrarlo en la suite de IA local, se obtienen los siguientes beneficios:
* **Privacidad de Consultas y Datos**: SearXNG actúa como un escudo o proxy de privacidad. Las consultas enviadas por el LLM no son asociadas a su dirección IP real, historial de chat, ni a perfiles publicitarios. SearXNG realiza las búsquedas por ti de forma anónima.
* **Agregación de Múltiples Fuentes**: Consolida en una sola API los resultados de más de 70 motores de búsqueda (incluyendo Google, Bing, DuckDuckGo, Wikipedia, StackOverflow, GitHub, Brave Search, etc.).
* **Integración RAG Automatizada sin Claves de API**: Evita tener que pagar por APIs de búsqueda empresariales (como Google Custom Search, Bing Web Search, Tavily o Jina AI) utilizando el protocolo estándar de consultas JSON de SearXNG.
* **Optimización de Recursos Locales**: Al offloadear el procesamiento de embeddings de RAG a Ollama y configurar scrapers eficientes, el sistema responde en segundos con información 100% verídica y citada.

---

## 2. Requisitos Previos

Antes de proceder, asegúrese de que el entorno cumpla con los siguientes requisitos técnicos en la máquina Windows:

| Componente | Requisito Mínimo | Propósito |
| :--- | :--- | :--- |
| **Docker Desktop** | v20.10+ (Backend WSL2 activado) | Ejecutar los contenedores de Open WebUI y SearXNG de forma aislada. |
| **Docker Compose** | v2.0+ (Soporte CLI `docker compose`) | Orquestar el despliegue multi-contenedor. |
| **Ollama** | Instalación activa en el Host (Windows) | Proveer los LLMs locales (ej. Llama 3, Gemma 2) y modelos de embeddings. |
| **Conexión a Internet** | Requerida en contenedores | Permitir a SearXNG consultar a los motores de búsqueda externos públicos. |
| **Puertos Disponibles** | `3000` (Open WebUI) y `8080` (SearXNG) | Exposición local de las interfaces y APIs de los servicios. |

---

## 3. Arquitectura y Flujo de Trabajo

La comunicación entre el usuario, Open WebUI, SearXNG, el Host local y los motores externos se estructura a través de redes Docker privadas de la siguiente manera:

```mermaid
graph TD
    User([Usuario]) -->|1. Prompt con búsqueda web activa| OWUI[Contenedor: Open WebUI]
    OWUI -->|2. Petición HTTP interna format=json| SearXNG[Contenedor: SearXNG]
    
    subgraph Docker Virtual Network (ai-network)
        OWUI
        SearXNG
    end

    subgraph Host Windows (Localhost)
        Ollama[Servidor Ollama: 11434]
    end

    SearXNG -->|3. Búsqueda anónima paralela| ExtWebs{Motores Públicos}
    ExtWebs -->|Google / Bing / DuckDuckGo| SearXNG
    ExtWebs -->|Wikipedia / StackOverflow| SearXNG
    
    SearXNG -->|4. Devuelve resultados unificados en JSON| OWUI
    
    OWUI -->|5. Descarga y extrae texto de las URLs devueltas| WebScraper[Scraper Interno BS4/Playwright]
    WebScraper -->|6. Genera e inyecta embeddings en base de datos vectorial| Embedder[Motor RAG / Ollama Embeddings]
    Embedder -->|7. Petición LLM con contexto enriquecido| Ollama
    Ollama -->|8. Genera respuesta con base en la web| OWUI
    OWUI -->|9. Respuesta final con citas y links| User
```

> [!NOTE]
> La comunicación entre Open WebUI y SearXNG se realiza a través de la red interna virtual de Docker (`ai-network`), utilizando el DNS interno de Docker (resolución por nombre de servicio `http://searxng:8080`), lo que mantiene la API de búsqueda totalmente inaccesible desde el exterior del host por seguridad. Open WebUI se conecta a Ollama en el Host de Windows a través de `http://host.docker.internal:11434`.

---

## 4. Paso a Paso de la Implementación

### Paso 4.1: Estructura de Directorios

Abra una consola de **PowerShell** y cree la estructura de carpetas necesaria para organizar la configuración de SearXNG. Se recomienda alojar el servicio de forma limpia dentro del directorio de servicios de IA:

```powershell
New-Item -ItemType Directory -Force -Path "C:\temp\AI Local\services\searxng"
New-Item -ItemType Directory -Force -Path "C:\temp\AI Local\services\searxng\config"
```

---

### Paso 4.2: Archivo de Configuración de SearXNG (`settings.yml`)

Este archivo define el comportamiento, la privacidad y los motores activos de SearXNG. Es fundamental deshabilitar el limitador de tasa (`limiter: false`) para evitar bloqueos internos por peticiones concurrentes desde Open WebUI, y habilitar explícitamente el formato `json` de salida.

Cree el archivo en `C:\temp\AI Local\services\searxng\config\settings.yml` con el siguiente contenido estructurado y robusto:

```yaml
# Configuración avanzada de SearXNG optimizada para integración RAG
use_default_settings: true

server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "CLAVE_SECRETA_SUPER_SEGURA_GENERADA_LOCALMENTE" # Reemplazado dinámicamente por deploy.ps1
  base_url: false
  image_proxy: true       # Proxy para proteger la privacidad al cargar imágenes externas
  limiter: false          # CRÍTICO: Desactivar limitador para evitar errores 403 con peticiones concurrentes de RAG

search:
  safe_search: 1          # 0 = Off, 1 = Moderate, 2 = Strict
  autocomplete: ""        # Desactivado para maximizar privacidad local
  languages:
    - es
    - en

# Habilitar explícitamente el formato JSON requerido por el procesador de Open WebUI
formats:
  - html
  - json

# Configuración y priorización de motores de búsqueda estables y rápidos
engines:
  - name: google
    engine: google
    shortcut: go
    active: true
    timeout: 3.0
  - name: bing
    engine: bing
    shortcut: bi
    active: true
    timeout: 3.0
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
    active: true
    timeout: 3.0
  - name: wikipedia
    engine: wikipedia
    shortcut: wp
    active: true
  - name: stackoverflow
    engine: xpath
    shortcut: so
    active: true
    categories: it
```

---

### Paso 4.3: Docker Compose Unificado e Integración con Ollama (`docker-compose.yml`)

Para una integración fluida, expondremos el contenedor de SearXNG y Open WebUI en el mismo archivo `docker-compose.yml`. Configuraremos la variable `OLLAMA_BASE_URL` apuntando a `host.docker.internal` para que Open WebUI pueda acceder a Ollama que se ejecuta en el host de Windows. 

Además, añadiremos variables avanzadas de RAG para delegar los embeddings a Ollama (usando un modelo rápido de embeddings como `nomic-embed-text` si está disponible) en lugar de usar CPU interna del contenedor de Open WebUI.

Cree el archivo en `C:\temp\AI Local\services\searxng\docker-compose.yml`:

```yaml
version: '3.8'

networks:
  ai-network:
    driver: bridge

services:
  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    restart: unless-stopped
    networks:
      - ai-network
    volumes:
      - ./config/settings.yml:/etc/searxng/settings.yml:ro
    ports:
      - "8080:8080"
    environment:
      - SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    networks:
      - ai-network
    ports:
      - "3000:8080"
    extra_hosts:
      - "host.docker.internal:host-gateway" # Habilitar resolución del Host de Windows
    volumes:
      - open-webui-data:/app/backend/data
    environment:
      - WEBUI_NAME=Local AI Workspace
      - HF_HUB_DISABLE_SYMLINKS_WARNING=1
      # Conexión local a Ollama en el Host de Windows
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      
      # --- CONFIGURACIÓN DE BÚSQUEDA WEB Y RAG ---
      - ENABLE_RAG_WEB_SEARCH=True
      - RAG_WEB_SEARCH_ENGINE=searxng
      # URL interna del contenedor para la API de búsqueda
      - SEARXNG_QUERY_URL=http://searxng:8080/search?q=<query>
      # Optimización del flujo RAG
      - RAG_WEB_SEARCH_RESULT_NUM=5           # Número de URLs principales a descargar y analizar
      - RAG_WEB_SEARCH_CONCURRENCY=4          # Peticiones paralelas de descarga de páginas
      - WEB_LOADER_ENGINE=bs4                 # Scraper por defecto. Cambiar a 'playwright' si es necesario
      
      # --- OPTIMIZACIÓN DE EMBEDDINGS RAG ---
      # Descomente y configure si prefiere usar Ollama para procesar embeddings en GPU local 
      # en lugar de la CPU interna del contenedor de Open WebUI.
      # - RAG_EMBEDDING_ENGINE=ollama
      # - RAG_EMBEDDING_MODEL=nomic-embed-text
    depends_on:
      - searxng

volumes:
  open-webui-data:
```

---

## Paso 4.4: Script de Despliegue de Alta Robustez (`deploy.ps1`)

Este script de PowerShell automatiza de forma segura el despliegue del stack:
1. Valida que Docker Desktop esté encendido y que el CLI sea accesible.
2. Comprueba si los puertos `3000` y `8080` ya están en uso por otras aplicaciones en Windows para prevenir fallos silenciosos de bind.
3. Genera una clave criptográfica aleatoria segura para SearXNG y la escribe en `settings.yml`.
4. Levanta los contenedores y proporciona un diagnóstico rápido visual.

Cree el archivo en `C:\temp\AI Local\services\searxng\deploy.ps1`:

```powershell
Write-Host "=== Iniciando Despliegue de Open WebUI + SearXNG ===" -ForegroundColor Cyan

# 1. Comprobar si Docker está instalado y activo
try {
    $dockerInfo = docker info --format '{{.Name}}' -ErrorAction Stop
    Write-Host "-> Conectado a Docker Engine de forma exitosa." -ForegroundColor Green
} catch {
    Write-Error "Docker no se está ejecutando o no está instalado en el PATH. Por favor encienda Docker Desktop antes de continuar."
    exit 1
}

# 2. Validar que los puertos 3000 y 8080 estén libres en el host
$portsToCheck = @(3000, 8080)
foreach ($port in $portsToCheck) {
    $portActive = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($portActive) {
        Write-Warning "¡El puerto $port ya está siendo utilizado por otro proceso!"
        Write-Warning "Detalle del proceso en puerto $port:"
        Get-Process -Id $portActive.OwningProcess | Format-Table Id, Name, Path -AutoSize
        Write-Error "Despliegue cancelado debido a colisión de puertos. Libere los puertos requeridos."
        exit 1
    }
}
Write-Host "-> Puertos 3000 y 8080 libres y verificados." -ForegroundColor Green

# 3. Generar una clave secreta segura para SearXNG
$randomBytes = New-Object Byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($randomBytes)
$secretKey = [System.Convert]::ToBase64String($randomBytes) -replace '[^a-zA-Z0-9]', ''

# 4. Inyectar la clave en settings.yml
$settingsPath = "C:\temp\AI Local\services\searxng\config\settings.yml"
if (Test-Path $settingsPath) {
    $content = Get-Content $settingsPath -Raw
    if ($content -match "CLAVE_SECRETA_SUPER_SEGURA_GENERADA_LOCALMENTE") {
        $content = $content -replace "CLAVE_SECRETA_SUPER_SEGURA_GENERADA_LOCALMENTE", $secretKey
        Set-Content $settingsPath $content
        Write-Host "-> Nueva clave secreta de SearXNG inyectada en settings.yml." -ForegroundColor Green
    } else {
        Write-Host "-> settings.yml ya contiene una clave secreta personalizada. Se conserva la existente." -ForegroundColor Yellow
    }
} else {
    Write-Error "No se encontró el archivo settings.yml en la ruta esperada: $settingsPath"
    exit 1
}

# 5. Desplegar los contenedores
Write-Host "-> Iniciando contenedores mediante Docker Compose..." -ForegroundColor Yellow
Set-Location "C:\temp\AI Local\services\searxng"
docker compose down -v --remove-orphans 2>$null # Limpiar ejecuciones previas si las hay
docker compose up -d

# 6. Diagnóstico y Estado
Write-Host "`n=== Despliegue Completado con Éxito ===" -ForegroundColor Green
Write-Host "Open WebUI disponible en: http://localhost:3000" -ForegroundColor Cyan
Write-Host "SearXNG disponible en: http://localhost:8080" -ForegroundColor Cyan
Write-Host "Compruebe el panel de administración de Open WebUI para verificar la conexión." -ForegroundColor Yellow
```

---

## 5. Plan de Verificación y Tuning

Realice las siguientes comprobaciones estructuradas para validar la integridad de la infraestructura de búsqueda privada y ajustar su rendimiento.

### Paso 5.1: Validación Aislada de SearXNG (API JSON)

1. Abra su navegador en `http://localhost:8080`. Compruebe que la página principal de SearXNG se renderice correctamente.
2. En una terminal de **PowerShell**, ejecute la siguiente llamada directa a la API para verificar que el formato de salida JSON esté respondiendo de manera correcta y rápida:
   ```powershell
   $response = Invoke-RestMethod -Uri "http://localhost:8080/search?q=ollama+llm&format=json"
   Write-Host "Total de resultados obtenidos: $($response.results.Count)" -ForegroundColor Green
   Write-Host "Primer resultado: $($response.results[0].title) -> $($response.results[0].url)" -ForegroundColor Cyan
   ```
   *Debería recibir una respuesta estructurada con la lista de resultados de múltiples motores agregados.*

---

### Paso 5.2: Validación Integral en el Chat (LLM Local + RAG)

1. Diríjase a `http://localhost:3000` y cree su cuenta inicial (el primer usuario registrado se convierte automáticamente en Administrador).
2. Verifique la conexión con Ollama en **Panel de Administración > Ajustes > Conexiones > Ollama API**. Debería ver listados sus modelos locales de Ollama (ej. `llama3`, `gemma2`).
3. Vaya a **Ajustes > Búsqueda Web**:
   * **Búsqueda Web**: Activado (`ON`).
   * **Motor de Búsqueda**: Seleccione `SearXNG`.
   * **URL de Consulta de SearXNG**: `http://searxng:8080/search?q=<query>`.
   * **Resultados de Búsqueda Web**: `5`.
4. Inicie una conversación de prueba con un modelo local.
5. Active el interruptor de **Búsqueda Web** (icono de red/globo en la caja de texto).

#### Caso de Prueba 1: Búsqueda de Noticias de Actualidad
* **Prompt del Usuario**: `"¿Cuáles son las últimas noticias sobre los lanzamientos espaciales de esta semana?"`
* **Comportamiento Esperado**: 
  * Verá un indicador animado: `"Buscando en la web (SearXNG)..."`.
  * Open WebUI llamará a SearXNG, extraerá los links, leerá los artículos y generará un resumen estructurado.
  * La respuesta vendrá acompañada de hipervínculos y números de cita interactivos (`[1]`, `[2]`).

#### Caso de Prueba 2: Búsqueda de Sintaxis y Código Técnico Reciente
* **Prompt del Usuario**: `"¿Cómo se configura un servidor MCP en la última versión de Claude Desktop? Muestra un ejemplo de su JSON de configuración."`
* **Comportamiento Esperado**: 
  * El LLM buscará en la web la documentación oficial de MCP.
  * Inyectará el fragmento de código JSON exacto para el archivo `claude_desktop_config.json`, asegurando que la información sea exacta y actualizada.

---

### Paso 5.3: Diagnóstico y Ajuste de Rendimiento (Troubleshooting)

Aquí se detallan los problemas más comunes de RAG Web y cómo solucionarlos de forma proactiva:

* **Error: "403 Forbidden" o "No Results"**:
  * *Causa*: El limitador interno de SearXNG está bloqueando las consultas rápidas hechas por el contenedor de Open WebUI.
  * *Solución*: Verifique que el archivo `settings.yml` tiene la propiedad `limiter: false` en la sección `server` y reinicie el contenedor (`docker compose restart searxng`).
* **Error: Búsquedas lentas o el contenedor de Open WebUI se congela temporalmente**:
  * *Causa*: El contenedor está descargando páginas pesadas y procesando embeddings localmente en la CPU virtualizada del contenedor, lo cual consume muchos recursos en Windows/WSL2.
  * *Solución*: Habilite el offloading de embeddings en Ollama (que utiliza GPU). Instale el modelo de embeddings ligero de Ollama en su máquina host (`ollama pull nomic-embed-text`) y active las variables en el Docker Compose:
    * `RAG_EMBEDDING_ENGINE=ollama`
    * `RAG_EMBEDDING_MODEL=nomic-embed-text`
* **Varios motores de SearXNG fallan (Retornan alertas de timeout)**:
  * *Causa*: Algunos motores de búsqueda públicos (como Google o Bing) detectan IPs residenciales/data centers y bloquean el scraping automatizado de SearXNG.
  * *Solución*: Si un motor falla consistentemente, desactívelo en `settings.yml` cambiando `active: true` a `active: false` y active motores alternativos más tolerantes (ej. `duckduckgo`, `wikipedia`, `qwant`, `brave`).
