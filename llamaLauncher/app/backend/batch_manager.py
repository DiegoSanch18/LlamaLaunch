"""
Batch Script Manager for LlamaLaunch
====================================
Governs parsing, generating, backing up, and persisting .bat scripts
for local LLM inference models in G:\\My Drive\\AI Local\\models.
"""

import os
import re
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

def parse_batch_script(bat_path: Path) -> Dict[str, Any]:
    """
    Parses an existing .bat script to extract inference flags and parameters.
    """
    if not bat_path.exists() or not bat_path.is_file():
        return {"success": False, "error": f"Batch file not found: {bat_path}"}

    try:
        content = bat_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {e}"}

    config: Dict[str, Any] = {
        "success": True,
        "path": str(bat_path),
        "filename": bat_path.name,
        "has_backup": bat_path.with_suffix(".bat.bak").exists() or Path(str(bat_path) + ".bak").exists(),
        "raw_content": content,
        "port": 8080,
        "host": "0.0.0.0",
        "threads": 8,
        "context": 8192,
        "ngl": 99,
        "flash_attn": True,
        "cache_type_k": "q4_0",
        "cache_type_v": "q4_0",
        "temp": 0.7,
        "top_p": 0.95,
        "top_k": 40,
        "min_p": 0.05,
        "model_file": "",
        "mmproj_file": "",
        "alias": ""
    }

    # Extract port
    m_port = re.search(r'--port\s+(\d+)', content)
    if m_port:
        config["port"] = int(m_port.group(1))

    # Extract context size
    m_ctx = re.search(r'--ctx-size\s+(\d+)', content) or re.search(r'-c\s+(\d+)', content)
    if m_ctx:
        config["context"] = int(m_ctx.group(1))

    # Extract threads
    m_th = re.search(r'--threads\s+(\d+)', content) or re.search(r'-t\s+(\d+)', content)
    if m_th:
        config["threads"] = int(m_th.group(1))

    # Extract GPU layers (ngl)
    m_ngl = re.search(r'--n-gpu-layers\s+(\d+)', content) or re.search(r'-ngl\s+(\d+)', content)
    if m_ngl:
        config["ngl"] = int(m_ngl.group(1))

    # Flash attention
    if "--flash-attn off" in content or "-fa off" in content:
        config["flash_attn"] = False
    elif "--flash-attn on" in content or "-fa on" in content:
        config["flash_attn"] = True

    # Cache types
    m_ck = re.search(r'--cache-type-k\s+([A-Za-z0-9_]+)', content)
    if m_ck:
        config["cache_type_k"] = m_ck.group(1).lower()

    m_cv = re.search(r'--cache-type-v\s+([A-Za-z0-9_]+)', content)
    if m_cv:
        config["cache_type_v"] = m_cv.group(1).lower()

    # Sampling
    m_temp = re.search(r'--temp\s+([0-9.]+)', content)
    if m_temp:
        config["temp"] = float(m_temp.group(1))

    m_topp = re.search(r'--top-p\s+([0-9.]+)', content)
    if m_topp:
        config["top_p"] = float(m_topp.group(1))

    m_topk = re.search(r'--top-k\s+(\d+)', content)
    if m_topk:
        config["top_k"] = int(m_topk.group(1))

    m_minp = re.search(r'--min-p\s+([0-9.]+)', content)
    if m_minp:
        config["min_p"] = float(m_minp.group(1))

    # Model and mmproj variables
    m_mod = re.search(r'set\s+["\']?MODEL=(?:%BASEDIR%)?([^"\'\r\n]+)["\']?', content, re.IGNORECASE)
    if m_mod:
        config["model_file"] = Path(m_mod.group(1).strip()).name

    m_mmp = re.search(r'set\s+["\']?MMPROJ=(?:%BASEDIR%)?([^"\'\r\n]+)["\']?', content, re.IGNORECASE)
    if m_mmp:
        config["mmproj_file"] = Path(m_mmp.group(1).strip()).name

    m_alias = re.search(r'--alias\s+([a-zA-Z0-9_\-\.]+)', content)
    if m_alias:
        config["alias"] = m_alias.group(1)

    return config

def update_batch_script_content(content: str, updates: Dict[str, Any]) -> str:
    """
    Updates inference parameter flags in an existing .bat script content string.
    Preserves existing structure, environment variables, comments, and path definitions.
    """
    updated = content

    if "port" in updates and updates["port"] is not None:
        port = int(updates["port"])
        if re.search(r'--port\s+\d+', updated):
            updated = re.sub(r'--port\s+\d+', f'--port          {port}', updated)
        # Also update comments or echo if present
        updated = re.sub(r'Puerto\s*:\s*\d+', f'Puerto : {port}', updated)
        updated = re.sub(r'localhost:\d+', f'localhost:{port}', updated)

    if "context" in updates and updates["context"] is not None:
        ctx = int(updates["context"])
        if re.search(r'--ctx-size\s+\d+', updated):
            updated = re.sub(r'--ctx-size\s+\d+', f'--ctx-size      {ctx}', updated)
        elif re.search(r'-c\s+\d+', updated):
            updated = re.sub(r'-c\s+\d+', f'-c {ctx}', updated)

    if "threads" in updates and updates["threads"] is not None:
        th = int(updates["threads"])
        if re.search(r'--threads\s+\d+', updated):
            updated = re.sub(r'--threads\s+\d+', f'--threads       {th}', updated)
        elif re.search(r'-t\s+\d+', updated):
            updated = re.sub(r'-t\s+\d+', f'-t {th}', updated)
        else:
            # Insert after ctx-size or model if threads was not previously specified
            m_caret = re.search(r'(--ctx-size|-c)\s+\d+\s*\^', updated)
            if m_caret:
                updated = updated[:m_caret.end()] + f'\r\n  --threads       {th}          ^' + updated[m_caret.end():]
            else:
                m_single = re.search(r'(--ctx-size|-c)\s+\d+', updated)
                if m_single:
                    updated = updated[:m_single.end()] + f' --threads {th}' + updated[m_single.end():]
                else:
                    m_model = re.search(r'--model\s+\S+', updated)
                    if m_model:
                        updated = updated[:m_model.end()] + f' --threads {th}' + updated[m_model.end():]

    if "ngl" in updates and updates["ngl"] is not None:
        ngl = int(updates["ngl"])
        if re.search(r'--n-gpu-layers\s+\d+', updated):
            updated = re.sub(r'--n-gpu-layers\s+\d+', f'--n-gpu-layers  {ngl}', updated)
        elif re.search(r'-ngl\s+\d+', updated):
            updated = re.sub(r'-ngl\s+\d+', f'-ngl {ngl}', updated)

    if "flash_attn" in updates and updates["flash_attn"] is not None:
        fa_val = "on" if updates["flash_attn"] else "off"
        if re.search(r'--flash-attn\s+(on|off)', updated):
            updated = re.sub(r'--flash-attn\s+(on|off)', f'--flash-attn    {fa_val}', updated)
        elif re.search(r'-fa\s+(on|off)', updated):
            updated = re.sub(r'-fa\s+(on|off)', f'-fa {fa_val}', updated)

    if "cache_type_k" in updates and updates["cache_type_k"]:
        ck = str(updates["cache_type_k"]).lower()
        if re.search(r'--cache-type-k\s+[A-Za-z0-9_]+', updated):
            updated = re.sub(r'--cache-type-k\s+[A-Za-z0-9_]+', f'--cache-type-k  {ck}', updated)

    if "cache_type_v" in updates and updates["cache_type_v"]:
        cv = str(updates["cache_type_v"]).lower()
        if re.search(r'--cache-type-v\s+[A-Za-z0-9_]+', updated):
            updated = re.sub(r'--cache-type-v\s+[A-Za-z0-9_]+', f'--cache-type-v  {cv}', updated)

    if "temp" in updates and updates["temp"] is not None:
        temp = float(updates["temp"])
        if re.search(r'--temp\s+[0-9.]+', updated):
            updated = re.sub(r'--temp\s+[0-9.]+', f'--temp          {temp}', updated)

    if "top_p" in updates and updates["top_p"] is not None:
        topp = float(updates["top_p"])
        if re.search(r'--top-p\s+[0-9.]+', updated):
            updated = re.sub(r'--top-p\s+[0-9.]+', f'--top-p         {topp}', updated)

    if "top_k" in updates and updates["top_k"] is not None:
        topk = int(updates["top_k"])
        if re.search(r'--top-k\s+\d+', updated):
            updated = re.sub(r'--top-k\s+\d+', f'--top-k         {topk}', updated)

    if "min_p" in updates and updates["min_p"] is not None:
        minp = float(updates["min_p"])
        if re.search(r'--min-p\s+[0-9.]+', updated):
            updated = re.sub(r'--min-p\s+[0-9.]+', f'--min-p         {minp}', updated)

    return updated

def generate_batch_template(
    model_folder: Path,
    model_filename: str,
    mmproj_filename: Optional[str] = None,
    family_name: str = "",
    variant_name: str = ""
) -> str:
    """
    Generates a calibrated .bat script template matching AI Local workstation standards.
    Uses dynamic %~dp0 routes, conditional mmproj detection, and auto fallback for binaries.
    """
    display_title = f"{family_name} {variant_name}".strip() or model_folder.name
    alias_slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', display_title.lower()).strip('-')

    mmproj_section = ""
    mmproj_arg = ""
    if mmproj_filename:
        mmproj_section = f"""
:: Priorizar proyector multimodal
if exist "%BASEDIR%{mmproj_filename}" (
    set "MMPROJ=%BASEDIR%{mmproj_filename}"
    set "MMPROJ_FLAG=--mmproj "!MMPROJ!""
) else (
    set "MMPROJ="
    set "MMPROJ_FLAG="
)
"""
    else:
        mmproj_section = """
:: Proyector multimodal no detectado inicialmente
set "MMPROJ_FLAG="
"""

    template = f"""@echo off
setlocal enabledelayedexpansion

:: =============================================================
::  {display_title} — llama-server (Inferencia Local)
::  Optimizado para: NVIDIA GeForce RTX 5060 Ti (16 GB VRAM)
::  Endpoint OpenAI compatible: http://localhost:8080/v1
:: =============================================================

set "BASEDIR=%~dp0"
set "MODEL=%BASEDIR%{model_filename}"
{mmproj_section}
:: Deteccion inteligente de la carpeta de binarios de llama.cpp
if exist "%BASEDIR%llama.cpp\\llama-server.exe" (
    set "BINDIR=%BASEDIR%llama.cpp"
) else if exist "%BASEDIR%..\\llama.cpp\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\llama.cpp"
) else if exist "%BASEDIR%..\\..\\llama.cpp\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\..\\llama.cpp"
) else if exist "%BASEDIR%..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64"
) else if exist "%BASEDIR%..\\..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64"
) else if exist "%BASEDIR%..\\..\\..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\..\\..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64"
) else if exist "%BASEDIR%..\\..\\..\\..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\..\\..\\..\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64"
) else if exist "%BASEDIR%..\\Bonsai 2\\llama.cpp\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\Bonsai 2\\llama.cpp"
) else if exist "%BASEDIR%..\\..\\Bonsai 2\\llama.cpp\\llama-server.exe" (
    set "BINDIR=%BASEDIR%..\\..\\Bonsai 2\\llama.cpp"
) else if exist "C:\\git\\LlamaLaunch\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64\\llama-server.exe" (
    set "BINDIR=C:\\git\\LlamaLaunch\\llamaLauncher\\bin\\llama.cpp\\llama-b9297-bin-win-cuda-x64"
) else (
    set "BINDIR="
)

if not "%BINDIR%"=="" (
    set "PATH=%BINDIR%;%PATH%"
    set "SERVER_EXE=%BINDIR%\\llama-server.exe"
) else (
    set "SERVER_EXE=llama-server.exe"
)

echo =====================================================================
echo  Iniciando {display_title}
echo  Servidor API    : http://localhost:8080/v1
echo  Web UI Integrada: http://localhost:8080
echo =====================================================================
echo.

if not exist "%MODEL%" (
    echo [ERROR] No se encontro el archivo del modelo:
    echo "%MODEL%"
    pause
    exit /b 1
)

"%SERVER_EXE%" ^
  --model         "%MODEL%"  ^
  !MMPROJ_FLAG!              ^
  --n-gpu-layers  99         ^
  --flash-attn    on         ^
  --ctx-size      16384      ^
  --ubatch-size   512        ^
  --cache-type-k  q4_0       ^
  --cache-type-v  q4_0       ^
  --threads       8          ^
  --temp          0.7        ^
  --top-p         0.95       ^
  --min-p         0.05       ^
  --host          0.0.0.0    ^
  --port          8080       ^
  --alias         {alias_slug}

echo.
echo Servidor detenido.
pause
endlocal
"""
    return template

def save_batch_script(bat_path: Path, content: str, create_backup: bool = True) -> Dict[str, Any]:
    """
    Persists script content with CRLF newlines and automatic .bat.bak backup creation.
    """
    try:
        bat_path.parent.mkdir(parents=True, exist_ok=True)

        backup_created = False
        backup_path = bat_path.with_suffix(".bat.bak")

        # 1. Create backup if requested and file already exists
        if create_backup and bat_path.exists():
            shutil.copy2(bat_path, backup_path)
            backup_created = True

        # 2. Normalize newlines to CRLF for Windows Batch files
        normalized_content = content.replace("\r\n", "\n").replace("\n", "\r\n")

        # 3. Write file
        with open(bat_path, "w", encoding="utf-8", newline="") as f:
            f.write(normalized_content)

        return {
            "success": True,
            "path": str(bat_path),
            "backup_created": backup_created,
            "backup_path": str(backup_path) if backup_created else None,
            "bytes_written": len(normalized_content)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save script: {str(e)}"
        }
