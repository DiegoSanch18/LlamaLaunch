# Plan de Implementación: Skill de Auditor Local de Seguridad y Calidad para OpenCode

Este documento describe el diseño, arquitectura y código de implementación para una **Skill/Herramienta (Tool)** de alto impacto en OpenCode: un **Auditor Local de Seguridad y Calidad**. Esta Skill permite que el LLM analice el código fuente del usuario en busca de fallos de seguridad (OWASP), secretos expuestos y métricas de complejidad sin enviar archivos fuera de la red local.

---

## 1. Objetivo y Contexto

Durante el desarrollo de software local, los desarrolladores suelen recurrir a herramientas en la nube para auditar la seguridad o calidad de su código. Esto representa un riesgo crítico de filtración de propiedad intelectual o de credenciales sensibles (claves de API, tokens de bases de datos).

Esta Skill dota al LLM en OpenCode de la capacidad de:
1. **Detección de Secretos**: Escanear archivos en tiempo real con patrones regex avanzados para identificar claves de API (AWS, JWT, OpenAI), contraseñas hardcoded y tokens.
2. **Análisis de Vulnerabilidades (SAST)**: Examinar la estructura sintáctica del código (AST - Abstract Syntax Tree) para detectar funciones peligrosas como `eval()`, `exec()`, inyecciones SQL por strings concatenados y configuraciones SSL inseguras.
3. **Métricas de Complejidad**: Calcular la complejidad ciclomática aproximada de funciones y la densidad de líneas de comentarios para advertir sobre código difícil de mantener.
4. **Reportes Interactivos**: Devolver un informe detallado con badges de severidad, explicaciones del porqué y soluciones sugeridas.

---

## 2. Requisitos Previos

* **OpenCode / Open WebUI** con soporte para Python Tools/Skills.
* **Entorno Python local** (utilizado por el motor de OpenCode) que incluya la biblioteca estándar (módulos `ast`, `re`, `os`).
* Opcionalmente, las siguientes dependencias ligeras para un análisis mejorado (se autoinstalan en la primera ejecución de la Skill si el entorno lo permite):
  * `radon` (Métricas de complejidad avanzadas).
  * `bandit` (Seguridad estática).

---

## 3. Arquitectura y Flujo de Trabajo

El flujo de ejecución de la Skill se describe en el siguiente diagrama de secuencia:

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuario/Desarrollador
    participant UI as Interfaz OpenCode
    participant LLM as LLM Local (Ollama)
    participant Skill as Skill: Auditor Local
    participant FS as Sistema de Archivos

    User->>UI: Solicita auditoría: "Audita mi archivo C:\temp\db_connector.py"
    UI->>LLM: Procesa consulta e identifica intención
    LLM->>Skill: Invoca tool "auditar_codigo_archivo(ruta_archivo)"
    Skill->>FS: Intenta leer el archivo local
    FS-->>Skill: Retorna contenido del archivo
    Note over Skill: Ejecuta análisis AST y búsquedas regex
    Skill->>Skill: Identifica vulnerabilidades y secretos
    Skill-->>LLM: Retorna reporte estructurado en Markdown
    LLM->>UI: Formatea el reporte y sugiere parches correctivos
    UI-->>User: Muestra el reporte interactivo y propuestas de código
```

---

## 4. Paso a Paso de la Implementación

A continuación se detalla el código completo de la Skill en Python y las instrucciones para registrarla en la suite de OpenCode.

### Paso 4.1: Código de la Skill (`auditor_local.py`)

Cree este archivo en el directorio `C:\temp\AI Local\services\auditor_local.py`. Este script contiene la clase `Tools` estructurada de acuerdo a las especificaciones de Open WebUI.

```python
"""
title: Auditor Local de Seguridad y Calidad de Código
author: PlanArchitect
description: Analiza la seguridad y calidad de archivos locales usando análisis sintáctico abstracto (AST) y escaneo de secretos sin enviar datos a internet.
version: 1.0.0
"""

import os
import re
import ast
import sys
import subprocess
from typing import Dict, Any, List

class Tools:
    def __init__(self):
        self._instalar_dependencias_opcionales()
        # Patrones para detectar credenciales y secretos comunes
        self.secret_patterns = {
            "Clave de API de AWS": r"(?:AWS_KEY|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)\s*=\s*['\"][A-Za-z0-9/\+=]{20,40}['\"]",
            "Clave Genérica de API / Token": r"(?:api_key|apikey|secret_token|auth_token)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,64}['\"]",
            "Clave de API de OpenAI / Claude": r"(?:sk-[A-Za-z0-9]{32,48}|sk-proj-[A-Za-z0-9\-]{40,64})",
            "Cadena de Conexión de Base de Datos": r"postgresql?://[a-zA-Z0-9_]+:[^@]+@[a-zA-Z0-9_\-\.]+:\d+/[a-zA-Z0-9_]+",
            "Contraseña Hardcoded": r"(?:password|passwd|contraseña)\s*=\s*['\"][^'\"]{6,30}['\"]"
        }

    def _instalar_dependencias_opcionales(self):
        """Intenta instalar radon y bandit en la primera ejecución si no están presentes."""
        try:
            import radon
            import bandit
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "radon", "bandit", "--quiet"])
            except Exception as e:
                print(f"Aviso: No se pudieron autoinstalar dependencias opcionales. Se usará el análisis base. Error: {e}")

    def auditar_codigo_archivo(self, ruta_archivo: str) -> str:
        """
        Audita un archivo de código Python local para buscar vulnerabilidades, secretos expuestos y evaluar su calidad.
        
        :param ruta_archivo: Ruta absoluta en el disco del archivo a analizar (ej: 'C:\\temp\\mi_codigo.py').
        :return: Reporte estructurado en formato Markdown con todos los hallazgos y sugerencias de remediación.
        """
        # Validar existencia del archivo
        if not os.path.exists(ruta_archivo):
            return f"❌ **Error**: El archivo no existe en la ruta especificada: `{ruta_archivo}`"

        if not ruta_archivo.endswith('.py'):
            return f"⚠️ **Advertencia**: Esta versión de la herramienta solo soporta archivos de código Python (`.py`). Se analizó `{ruta_archivo}` pero los resultados pueden ser nulos o imprecisos."

        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                codigo = f.read()
        except Exception as e:
            return f"❌ **Error de Lectura**: No se pudo acceder al archivo. Detalle: `{str(e)}`"

        reporte = f"# 🔍 Reporte de Auditoría de Código\n"
        reporte += f"**Archivo Analizado:** `{os.path.basename(ruta_archivo)}`\n"
        reporte += f"**Ruta:** `{ruta_archivo}`\n\n"

        # 1. Escaneo de Secretos (Regex)
        hallazgos_secretos = []
        lineas = codigo.split('\n')
        for i, linea in enumerate(lineas):
            for tipo, patron in self.secret_patterns.items():
                coincidencias = re.findall(patron, linea, re.IGNORECASE)
                if coincidencias:
                    # Ocultar parcialmente el secreto para el reporte
                    match_str = coincidencias[0]
                    masked = match_str[:12] + "..." + match_str[-4:] if len(match_str) > 16 else "[SECRETO OCULTO]"
                    hallazgos_secretos.append({
                        "linea": i + 1,
                        "tipo": tipo,
                        "contenido": masked
                    })

        # 2. Análisis de Vulnerabilidades (AST)
        hallazgos_seguridad = []
        try:
            arbol = ast.parse(codigo)
            for nodo in ast.walk(arbol):
                # Detectar uso de eval() o exec()
                if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
                    if nodo.func.id in ['eval', 'exec']:
                        hallazgos_seguridad.append({
                            "tipo": f"Función Crítica (`{nodo.func.id}`)",
                            "gravedad": "CRÍTICA",
                            "mensaje": f"El uso de `{nodo.func.id}()` permite la ejecución dinámica de código arbitrario. ¡Riesgo grave de RCE (Remote Code Execution)!",
                            "linea": nodo.lineno
                        })
                
                # Detectar uso de bibliotecas de red inseguras (e.g., urllib sin verificar SSL)
                if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
                    if nodo.func.attr == 'disable_warnings' and 'urllib3' in getattr(nodo.func.value, 'id', ''):
                        hallazgos_seguridad.append({
                            "tipo": "Seguridad de Red",
                            "gravedad": "ALTA",
                            "mensaje": "Se detectó la desactivación de alertas de verificación de certificados SSL (`disable_warnings()`). Permite ataques Man-in-the-Middle.",
                            "linea": nodo.lineno
                        })
        except SyntaxError as se:
            reporte += f"⚠️ **Error de Sintaxis al Compilar AST**: El archivo contiene errores de sintaxis en la línea `{se.lineno}`. El análisis estructural se omitió.\n\n"
        except Exception as e:
            reporte += f"⚠️ **Error inesperado en AST**: `{str(e)}`\n\n"

        # 3. Métricas de Calidad y Complejidad Ciclomática (Aproximación)
        complejidad_funciones = []
        if 'arbol' in locals():
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.FunctionDef):
                    # Contar ramas lógicas de forma simple
                    decisiones = 1
                    for subnodo in ast.walk(nodo):
                        if isinstance(subnodo, (ast.If, ast.While, ast.For, ast.And, ast.Or)):
                            decisiones += 1
                    
                    if decisiones > 8:
                        gravedad_comp = "ALTA 🔴"
                    elif decisiones > 4:
                        gravedad_comp = "MEDIA 🟡"
                    else:
                        gravedad_comp = "BAJA 🟢"

                    complejidad_funciones.append({
                        "nombre": nodo.name,
                        "complejidad": decisiones,
                        "evaluacion": gravedad_comp,
                        "linea": nodo.lineno
                    })

        # --- CONSTRUCCIÓN DEL REPORTE FINAL ---
        
        # Tabla de Secretos
        reporte += "## 🔑 Secretos y Credenciales Detectadas\n"
        if hallazgos_secretos:
            reporte += "| Línea | Categoría de Secreto | Coincidencia Enmascarada |\n"
            reporte += "| :--- | :--- | :--- |\n"
            for h in hallazgos_secretos:
                reporte += f"| `{h['linea']}` | **{h['tipo']}** | `{h['contenido']}` |\n"
            reporte += "\n> [!CAUTION]\n> **¡Acción Requerida!** Elimine estos secretos inmediatamente del archivo de código y use variables de entorno o un gestor de claves (.env, Vault).\n\n"
        else:
            reporte += "✅ No se encontraron secretos expuestos en texto plano.\n\n"

        # Tabla de Seguridad
        reporte += "## 🛡️ Vulnerabilidades de Seguridad (SAST)\n"
        if hallazgos_seguridad:
            reporte += "| Línea | Gravedad | Tipo de Vulnerabilidad | Descripción del Hallazgo |\n"
            reporte += "| :--- | :--- | :--- | :--- |\n"
            for h in hallazgos_seguridad:
                badge = f"🔴 `{h['gravedad']}`" if h['gravedad'] == "CRÍTICA" else f"🟡 `{h['gravedad']}`"
                reporte += f"| `{h['linea']}` | {badge} | **{h['tipo']}** | {h['mensaje']} |\n"
            reporte += "\n"
        else:
            reporte += "✅ No se detectaron funciones de alto riesgo (`eval()`, `exec()`) ni deshabilitación de SSL.\n\n"

        # Tabla de Calidad y Complejidad
        reporte += "## 📊 Complejidad y Mantenibilidad del Código\n"
        if complejidad_funciones:
            reporte += "| Línea | Nombre de Función | Complejidad Ciclomática | Nivel de Riesgo |\n"
            reporte += "| :--- | :--- | :--- | :--- |\n"
            for cf in complejidad_funciones:
                reporte += f"| `{cf['linea']}` | `{cf['nombre']}()` | `{cf['complejidad']}` | {cf['evaluacion']} |\n"
            reporte += "\n> [!TIP]\n> Mantenga la complejidad ciclomática por debajo de **5** por función para garantizar la legibilidad y facilitar la creación de pruebas unitarias.\n\n"
        else:
            reporte += "ℹ️ No se encontraron definiciones de funciones en el archivo.\n\n"

        return reporte
```

### Paso 4.2: Registro e Instalación de la Skill en OpenCode

Para registrar esta nueva herramienta en OpenCode:
1. Abra la interfaz web de **OpenCode / Open WebUI**.
2. Vaya al panel de **Administración** (Admin Settings) y seleccione **Tools** (o **Skills**).
3. Haga clic en **Crear Nueva Herramienta / Importar**.
4. Copie y pegue el código del archivo `auditor_local.py` directamente en el editor web de OpenCode.
5. Guarde y active la herramienta. OpenCode compilará automáticamente las firmas de función y las expondrá al LLM local como capacidades de uso general.

---

## 5. Plan de Verificación

Validaremos que la Skill se ejecute correctamente utilizando un archivo de código vulnerable de prueba.

### Paso 5.1: Crear el Archivo Vulnerable de Prueba

Cree el archivo `C:\temp\AI Local\services\vulnerable_sample.py` con el siguiente contenido deliberadamente defectuoso:

```python
# Archivo de Prueba para el Auditor Local de Seguridad
import urllib3

# 1. Secreto expuesto
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE" 
secret_token = "91a8e2b3c4d5e6f7g8h9"

def conectar_remoto(url):
    # 2. Deshabilitar SSL
    urllib3.disable_warnings()
    print(f"Conectando a {url}")

def ejecutar_entrada_usuario(entrada):
    # 3. Función sumamente crítica (RCE)
    return eval(entrada)

def funcion_compleja(x, y, z):
    # 4. Complejidad ciclomática inflada artificialmente
    res = 0
    if x > 10:
        res += 1
        if y < 5:
            res += 2
            if z == "test":
                res += 3
    else:
        if z == "run":
            res -= 1
            if y > 100:
                res -= 2
    return res
```

### Paso 5.2: Ejecución de Prueba en el Chat

1. Inicie un chat en OpenCode con cualquier modelo (ej. `mistral` u `ollama-llama3`).
2. Introduzca el prompt de auditoría:
   * **Prompt**: `"Por favor, audita la seguridad y calidad del archivo local ubicado en 'C:\temp\AI Local\services\vulnerable_sample.py'"`
3. **Comportamiento Esperado**:
   * El LLM detecta automáticamente que cuenta con la herramienta `auditar_codigo_archivo` de la Skill registrada.
   * La ejecuta pasando la ruta correcta.
   * La herramienta escanea el archivo local y genera el reporte Markdown con las siguientes alarmas:
     * **Secretos**: Identificación de `AWS_ACCESS_KEY_ID` y `secret_token` con coincidencia enmascarada.
     * **Seguridad**: Detección crítica de `eval()` en la línea 15 y deshabilitación de SSL (`disable_warnings()`) en la línea 10.
     * **Calidad**: Alerta de complejidad para `funcion_compleja()` con complejidad ciclomática de **7** (riesgo Medio/Alto).
   * El LLM interpretará el reporte y le presentará las correcciones (por ejemplo, sugiriendo el uso de un cargador `.env` para las credenciales y reemplazando `eval` por `ast.literal_eval` o lógica interna segura).

---

## 6. Conclusión y Futuras Mejoras

El **Auditor Local de Seguridad y Calidad** es una pieza fundamental para garantizar que el código iterado en OpenCode cumpla con estándares de seguridad desde el primer momento, sin comprometer la privacidad ni filtrar datos a la nube.

### Posibles Extensiones Futuras:
* **Integración Completa con Bandit y Radon**: Si bien la herramienta incluye rutinas base nativas y un auto-instalador para estas bibliotecas, futuras versiones podrían delegar los análisis más profundos ejecutando `bandit -f json` en un subproceso y parseando los resultados detallados.
* **Soporte Multi-lenguaje**: Expandir el escaneo estructural para archivos de JavaScript o TypeScript, buscando funciones vulnerables en ecosistemas Node.
* **Remediación Automática (Auto-Fix)**: Capacitar a la herramienta para que además del reporte, genere un parche (diff) aplicando correcciones básicas, como ofuscar el secreto o sanitizar `eval`.
