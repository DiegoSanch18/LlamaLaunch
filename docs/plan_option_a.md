# Plan de Implementación: Servidor MCP de SQLite Database para la Suite de OpenCode

Este documento detalla la instalación, configuración e integración de un servidor **Model Context Protocol (MCP)** para SQLite Database en la suite de OpenCode. Esto permite que los modelos de lenguaje locales interactúen de forma segura, estructurada y totalmente offline con bases de datos relacionales.

---

## 1. Objetivo y Contexto

El acceso de los Modelos de Lenguaje (LLMs) a bases de datos relacionales ha estado tradicionalmente limitado a la generación de código SQL que el usuario debe ejecutar manualmente, o a integraciones propietarias en la nube. 

Este plan de implementación resuelve este problema de forma local y privada al desplegar un **Servidor MCP SQLite**. Mediante este protocolo, el LLM adquiere capacidades nativas para:
- Inspeccionar esquemas de bases de datos (tablas, columnas, tipos de datos, claves foráneas).
- Ejecutar consultas de lectura y agregación (`SELECT`, `GROUP BY`, `JOIN`).
- Modificar esquemas de forma controlada y realizar inserciones/actualizaciones mediante la aprobación expresa del usuario.
- Analizar datos estructurados complejos directamente desde el motor local.

### Beneficios Clave
* **Privacidad Absoluta**: Todo el procesamiento de datos y la ejecución SQL ocurren en la máquina local, sin enviar datos a APIs externas.
* **Seguridad de Contexto**: El LLM solo accede a la base de datos a través de herramientas bien definidas provistas por el servidor MCP, mitigando inyecciones maliciosas accidentales.
* **Desempeño Offline**: Funciona completamente sin conexión a Internet.

---

## 2. Requisitos Previos

Antes de comenzar, asegúrese de contar con los siguientes elementos instalados en el sistema:

| Componente | Requisito Mínimo | Propósito |
| :--- | :--- | :--- |
| **Node.js** | v18.0.0 o superior | Entorno de ejecución para el servidor MCP oficial de SQLite. |
| **npm / npx** | v9.0.0 o superior | Administrador de paquetes para descargar y ejecutar el servidor. |
| **OpenCode Suite / Open WebUI** | Versión compatible con MCP | Interfaz de chat y cliente MCP principal. |
| **SQLite CLI** | Opcional (recomendado) | Herramienta de línea de comandos para verificar archivos `.db` externamente. |
| **Permisos de Escritura** | Lectura/Escritura en directorio local | Necesario para crear y modificar el archivo de base de datos `.db`. |

---

## 3. Arquitectura y Flujo de Trabajo

El flujo de comunicación entre el usuario, el LLM local, la suite OpenCode y el motor de base de datos SQLite se estructura de la siguiente manera:

```mermaid
graph TD
    User([Usuario]) -->|1. Envía Prompt: '¿Cuántos clientes tenemos?'| UI[Interfaz de OpenCode]
    UI -->|2. Envía Contexto y Herramientas| LLM[LLM Local / Ollama]
    LLM -->|3. Decide usar herramienta 'query'| MCP_Client[Cliente MCP en OpenCode]
    MCP_Client -->|4. Llama por JSON-RPC (stdio)| MCP_Server[Servidor MCP SQLite]
    MCP_Server -->|5. Ejecuta Consulta SQL| DB[(Base de Datos SQLite .db)]
    DB -->|6. Retorna Filas de Datos| MCP_Server
    MCP_Server -->|7. Devuelve Resultado JSON| MCP_Client
    MCP_Client -->|8. Añade Datos al Contexto| LLM
    LLM -->|9. Genera Respuesta Natural| UI
    UI -->|10. Muestra Respuesta Formateada| User
```

> [!IMPORTANT]
> El canal de comunicación entre el cliente MCP (OpenCode) y el servidor MCP se realiza a través de **Standard Input/Output (stdio)** mediante mensajes JSON-RPC. Es vital que el servidor no escriba logs informativos en `stdout`, ya que corrompería el canal de datos. Todo log de depuración debe dirigirse a `stderr`.

---

## 4. Paso a Paso de la Implementación

A continuación, se detallan los pasos exactos para configurar el Servidor MCP de SQLite en Windows, adaptado tanto para ejecución nativa como para contenedores Docker.

### Paso 4.1: Preparar la Base de Datos de Prueba (Vía Python - 100% Offline y Seguro)

Para evitar problemas de compilación de binarios nativos de C++ con `sqlite3` en Node.js sobre Windows, utilizaremos **Python** y su biblioteca estándar `sqlite3` (ya incluida en cualquier instalación de Python). Esto garantiza una ejecución inmediata, sin dependencias de red ni compiladores.

1. Abra una terminal de **PowerShell** y cree la estructura de directorios:
   ```powershell
   New-Item -ItemType Directory -Force -Path "C:\temp\AI Local\services\sqlite"
   ```

2. Cree un script de inicialización en la ruta `C:\temp\AI Local\services\sqlite\init_db.py`:

   ```python
   import os
   import sqlite3

   # Definir rutas absolutas
   db_dir = r"C:\temp\AI Local\services\sqlite"
   db_path = os.path.join(db_dir, "inventario.db")

   # Asegurar existencia de directorio
   os.makedirs(db_dir, exist_ok=True)

   # Limpiar archivo previo para creación pura
   if os.path.exists(db_path):
       try:
           os.remove(db_path)
       except PermissionError:
           print(f"Error: La base de datos en {db_path} está en uso. Cierre las conexiones antes de re-inicializar.")
           exit(1)

   # Conectar y estructurar base de datos
   conn = sqlite3.connect(db_path)
   cursor = conn.cursor()

   # 1. Crear tabla de productos
   cursor.execute('''
       CREATE TABLE productos (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           nombre TEXT NOT NULL,
           categoria TEXT NOT NULL,
           precio REAL NOT NULL,
           stock INTEGER NOT NULL
       )
   ''')

   # 2. Insertar registros iniciales de prueba
   productos = [
       ("Servidor NAS Synology", "Almacenamiento", 450.00, 12),
       ("Disco Duro Red Pro 8TB", "Almacenamiento", 220.50, 45),
       ("Switch TP-Link 24 Puertos", "Redes", 110.00, 8),
       ("Router WiFi 6 ASUS", "Redes", 189.99, 15),
       ("Cámara de Seguridad IP", "Seguridad", 75.25, 30)
   ]

   cursor.executemany(
       "INSERT INTO productos (nombre, categoria, precio, stock) VALUES (?, ?, ?, ?)",
       productos
   )

   conn.commit()
   conn.close()

   print(f"¡Base de datos SQLite inicializada exitosamente en: {db_path}!")
   ```

3. Ejecute el script con Python desde la consola de comandos o PowerShell:
   ```powershell
   python "C:\temp\AI Local\services\sqlite\init_db.py"
   ```

---

### Paso 4.2: Descargar e Instalar el Servidor MCP

El servidor oficial MCP de SQLite se distribuye a través del registro npm de Node.js. En Windows, podemos instalarlo globalmente para garantizar que el ejecutable esté listo en el PATH del sistema.

```powershell
npm install -g @modelcontextprotocol/server-sqlite
```

> [!TIP]
> **Instalación Offline**: Si no cuenta con conexión a Internet en la máquina de despliegue, descargue el paquete en un equipo conectado usando `npm pack @modelcontextprotocol/server-sqlite` y transfiera el archivo `.tgz` resultante para instalarlo de forma aislada:
> `npm install -g .\modelcontextprotocol-server-sqlite-<version>.tgz`

---

### Paso 4.3: Integración y Configuración del Cliente MCP

Dependiendo de su arquitectura de chat preferida, el servidor MCP de SQLite se puede integrar en dos modalidades:

#### Opción A: Integración Nativa en OpenCode CLI / Claude Desktop
Si ejecuta los modelos de forma nativa en su consola o en el cliente de escritorio, puede añadir el servidor editando el archivo de configuración de MCP:
* **OpenCode CLI**: `~/.config/opencode/opencode.json` o `%USERPROFILE%\.config\opencode\opencode.json`
* **Claude Desktop**: `%APPDATA%\Roaming\EasySystem\Claude\claude_desktop_config.json`

Añada el bloque de configuración del servidor en la sección `"mcpServers"`:

```json
{
  "mcpServers": {
    "sqlite-local": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sqlite",
        "--db-path",
        "C:\\temp\\AI Local\\services\\sqlite\\inventario.db"
      ],
      "env": {
        "PATH": "C:\\Program Files\\nodejs\\;%PATH%"
      }
    }
  }
}
```

#### Opción B: Integración en Open WebUI (Ejecución bajo Docker-Compose)
Dado que Open WebUI se ejecuta en un contenedor Docker aislado (`open-webui/docker-compose.yml`), el contenedor no puede llamar directamente a comandos `npx` de la máquina host de Windows. Para habilitar la base de datos de manera limpia, se exponen dos métodos:

1. **Montaje de Volumen y Servidor Interno**:
   Añada el archivo `.db` al contenedor de Open WebUI mapeando la carpeta SQLite en el archivo `docker-compose.yml`:
   ```yaml
   services:
     open-webui:
       # ... configuración existente ...
       volumes:
         - open-webui-data:/app/backend/data
         - C:\temp\AI Local\services\sqlite:/app/backend/sqlite:ro # Base de datos montada en Solo Lectura
   ```
   Y configure el servidor SQLite directamente dentro del panel administrativo de la interfaz de Open WebUI (**Settings > Connections > MCP**), usando una conexión SSE si despliega un contenedor MCP de soporte, o stdio si su imagen personalizada incluye Node.js.

---

### Paso 4.4: Alineación de Seguridad con `tool_permissions.json`

Para proteger el entorno local de modificaciones destructivas no deseadas, las herramientas proporcionadas por el servidor SQLite deben clasificarse según la política de seguridad interactiva de OpenCode (`tool_permissions.json`):

| Herramienta MCP | Acción SQL Equivalente | Nivel de Riesgo | Confirmación Explicativa |
| :--- | :--- | :--- | :--- |
| `list_tables` | Ver esquema global de DB | **Bajo** (`low`) | **Auto-aprobado** (No altera datos) |
| `describe_table` | Detalle estructural de columnas | **Bajo** (`low`) | **Auto-aprobado** (No altera datos) |
| `read_query` | Consultas `SELECT` | **Bajo** (`low`) | **Auto-aprobado** (Consultas de lectura) |
| `write_query` | Sentencias `INSERT`, `UPDATE`, `DELETE`, `ALTER` | **Medio/Alto** (`medium`) | **Requerido** (Muestra preview del SQL y pide confirmación manual) |

> [!CAUTION]
> NUNCA permita la auto-aprobación del comando `write_query`. Un query mal estructurado generado por el LLM podría truncar o eliminar tablas enteras. El cliente OpenCode debe aplicar el "Interactive Safety Gating" para esta herramienta en particular.

---

## 5. Plan de Verificación

Una vez finalizada la configuración del entorno SQLite y la integración en el cliente, realice el siguiente conjunto de pruebas estructuradas:

### Paso 5.1: Validación Aislada (Inspector MCP)

Antes de delegar la base de datos al LLM, pruebe el canal JSON-RPC y las funciones disponibles levantando el Inspector MCP oficial en PowerShell:

```powershell
npx @modelcontextprotocol/inspector npx -y @modelcontextprotocol/server-sqlite --db-path "C:\temp\AI Local\services\sqlite\inventario.db"
```

1. Abra un navegador en `http://localhost:5173`.
2. Verifique en la pestaña **Tools** que se expongan correctamente: `list_tables`, `describe_table`, `read_query` y `write_query`.
3. Ejecute una consulta manual `SELECT * FROM productos LIMIT 2;` y confirme la recepción correcta de la respuesta estructurada.

---

### Paso 5.2: Validación Integral en el Chat (LLM Local)

Inicie una conversación interactiva en su cliente de OpenCode o Open WebUI utilizando su modelo local (ej. Gemma 2 o Llama 3.2) y realice los siguientes casos de prueba:

#### Caso de Prueba 1: Descubrimiento de Estructuras (Read-Only Auto-Approved)
* **Prompt del Usuario**: `"¿Qué tablas tengo en mi base de datos de inventario y cuáles son las columnas de la tabla de productos?"`
* **Resultado Esperado**: El LLM debe llamar automáticamente a `list_tables` y luego a `describe_table`. Deberá presentar el listado de columnas (`id`, `nombre`, `categoria`, `precio`, `stock`) formateadas en una tabla Markdown clara.

#### Caso de Prueba 2: Consulta Analítica de Negocio
* **Prompt del Usuario**: `"¿Cuál es el valor económico total de nuestro inventario y cuántas unidades tenemos de productos de Almacenamiento?"`
* **Resultado Esperado**: El LLM deducirá la consulta SQL adecuada (ej. `SELECT SUM(precio * stock) FROM productos;` y `SELECT SUM(stock) FROM productos WHERE categoria = 'Almacenamiento';`), invocará `read_query` de forma silenciosa y formulará una respuesta conversacional y concisa en base a los datos recuperados.

#### Caso de Prueba 3: Intento de Modificación de Datos (Safety Gate Verification)
* **Prompt del Usuario**: `"Agrega un nuevo producto llamado 'Teclado Mecánico RGB' de la categoría 'Periféricos', con un precio de 89.99 y stock de 25."`
* **Resultado Esperado**:
  1. El LLM identificará la necesidad de ejecutar `write_query`.
  2. La suite de OpenCode interceptará la petición debido al nivel de riesgo `medium/high` definido en la política de seguridad.
  3. Se le presentará al usuario en pantalla una vista previa del código SQL generado:
     `INSERT INTO productos (nombre, categoria, precio, stock) VALUES ('Teclado Mecánico RGB', 'Periféricos', 89.99, 25);`
  4. El cambio solo se aplicará a la base de datos local tras la confirmación manual y explicativa del usuario.

