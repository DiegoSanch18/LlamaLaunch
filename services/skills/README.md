# Centro de MCP y Skills Locales 🧠🔌

> [!NOTE]
> Este directorio es el punto centralizado de control para todos los **Model Context Protocol (MCP) Servers** y **Skills** de nuestro entorno de Inteligencia Artificial local. Cualquier agente o copiloto de código (como OpenCode) debe leer esta guía para entender qué capacidades adicionales tiene a su disposición y dónde se encuentran configuradas.

---

## 🛠️ Estructura del Centro de Capacidades

El directorio `services/skills` está organizado de la siguiente manera:

```text
services/skills/
├── README.md                 # Este registro general
├── sqlite/                   # Servidor MCP de base de datos local
│   ├── init_db.py            # Script Python para inicializar/re-crear la base de datos
│   └── inventario.db         # Archivo SQLite de base de datos de inventario
├── Mermaid/                  # Manuales oficiales de sintaxis Mermaid.js (30 archivos .md)
└── mermaidDiagramGen/        # Skill para la generación de diagramas Mermaid
    ├── README.md             # Guía rápida en español
    └── SKILL.md              # Definición de la Skill para el agente de IA
```

---

## 🔌 1. Servidores MCP Activos

| Servidor | Tipo | Descripción | Ruta Base / Destino | Configuración Activa |
| :--- | :--- | :--- | :--- | :--- |
| **`sqlite-local`** | Base de Datos | MCP para interactuar con datos relacionales de un inventario local | [sqlite/inventario.db](file:///c:/temp/AI%20Local/services/skills/sqlite/inventario.db) | [opencode_config.json](file:///c:/temp/AI%20Local/services/opencode/opencode_config.json) |

> [!TIP]
> **Inicialización**: Si necesitas resetear o re-inicializar la base de datos de inventario con datos semilla de prueba, puedes ejecutar el script:
> ```bash
> python services/skills/sqlite/init_db.py
> ```
> El servidor MCP `sqlite-local` está montado en **Open WebUI** en modo lectura (RO) para visualizaciones y es de lectura/escritura total en **OpenCode** para tareas de administración.

---

## 🧠 2. Skills de Agente Disponibles

Las skills dotan a los modelos de lenguaje de "instrucciones del sistema" quirúrgicas sobre cómo resolver una tarea compleja de forma libre de fallos.

### 📊 Generador de Diagramas Mermaid (`mermaidDiagramGen`)
* **Ruta de la Skill**: [mermaidDiagramGen/SKILL.md](file:///c:/temp/AI%20Local/services/skills/mermaidDiagramGen/SKILL.md)
* **Descripción**: Capacita al agente para formular diagramas Mermaid.js altamente precisos y estéticamente premium libres de los bugs típicos de parser (como la palabra reservada `end` en minúscula o nombres de nodo con letra inicial `o`/`x`).
* **Dependencias**: Consume los manuales de sintaxis oficiales ubicados en [skills/Mermaid/](file:///c:/temp/AI%20Local/services/skills/Mermaid).

> [!WARNING]
> Al crear nuevas skills, asegúrate de crear una subcarpeta descriptiva (ej. `skills/miNuevaSkill`) y proveer un archivo `SKILL.md` con el frontmatter estándar (`name` y `description`) en formato YAML al inicio para que los agentes puedan auto-descubrirla e importarla.

---

## 🔒 Directivas de Seguridad

Siguiendo el estándar adaptado de **Claude Code**:
1. **Verificación de Comandos**: Las llamadas e interacciones del MCP que modifiquen datos de producción o ejecuten sentencias SQL destructivas (como `DROP TABLE` o `DELETE`) deben ser advertidas al usuario para su autorización interactiva.
2. **Respaldo Dinámico**: Antes de realizar cualquier cambio en la estructura del ecosistema de base de datos, confirma que el script de inicialización esté disponible para mitigar riesgos de pérdida de datos.
