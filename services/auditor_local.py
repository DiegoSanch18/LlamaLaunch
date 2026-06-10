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
