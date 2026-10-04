"""
Batch Script Manager for LlamaLaunch
====================================
Governs parsing, generating, backing up, and persisting .bat scripts
for local LLM inference models in G:\\My Drive\\AI Local\\models.
"""

import os
import re
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

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
        "cache_type_k": "f16",
        "cache_type_v": "f16",
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

    # Cache types
    m_ck = re.search(r'--cache-type-k\s+([A-Za-z0-9_]+)', content)
    if m_ck:
        config["cache_type_k"] = m_ck.group(1).lower()

    m_cv = re.search(r'--cache-type-v\s+([A-Za-z0-9_]+)', content)
    if m_cv:
        config["cache_type_v"] = m_cv.group(1).lower()

    # Flash attention
    if "--flash-attn off" in content or "-fa off" in content:
        config["flash_attn"] = False
    elif "--flash-attn on" in content or "-fa on" in content:
        config["flash_attn"] = True

    # KV cache quantization strictly requires Flash Attention in llama.cpp
    if m_ck and config.get("cache_type_k") not in ("f16", "none", None, ""):
        config["flash_attn"] = True

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

    # Check if MMPROJ is conditionally assigned with 'if exist'
    m_if_mmp = re.search(r'if\s+exist\s+["\']?(?:%BASEDIR%)?([^"\'\s]+)["\']?\s*\(\s*set\s+["\']?MMPROJ=', content, re.IGNORECASE)
    if m_if_mmp:
        cand_name = Path(m_if_mmp.group(1).strip()).name
        if (bat_path.parent / cand_name).exists():
            config["mmproj_file"] = cand_name
        else:
            config["mmproj_file"] = ""
    else:
        m_mmp = re.search(r'set\s+["\']?MMPROJ=(?:%BASEDIR%)?([^"\'\r\n]+)["\']?', content, re.IGNORECASE)
        cand_mmproj = Path(m_mmp.group(1).strip()).name if m_mmp else ""
        if not cand_mmproj:
            m_cli_mmp = re.search(r'--mmproj\s+["\']?(?:%BASEDIR%)?([^"\'\s]+)["\']?', content, re.IGNORECASE)
            if m_cli_mmp:
                cand_mmproj = Path(m_cli_mmp.group(1).strip()).name
        config["mmproj_file"] = cand_mmproj

    available_mmproj = config["mmproj_file"]
    if not available_mmproj:
        try:
            for f in bat_path.parent.glob("*mmproj*.gguf"):
                available_mmproj = f.name
                break
        except Exception:
            pass
    config["available_mmproj"] = available_mmproj
    config["vision_enabled"] = bool(config["mmproj_file"])

    m_alias = re.search(r'--alias\s+([a-zA-Z0-9_\-\.]+)', content)
    if m_alias:
        config["alias"] = m_alias.group(1)

    # Ubatch size
    m_ub = re.search(r'--ubatch-size\s+(\d+)', content)
    if m_ub:
        config["ubatch_size"] = int(m_ub.group(1))
    else:
        config["ubatch_size"] = 512

    # Repeat penalty
    m_rp = re.search(r'--repeat-penalty\s+([0-9.]+)', content)
    if m_rp:
        config["repeat_penalty"] = float(m_rp.group(1))

    # Speculative MTP
    m_st = re.search(r'--spec-type\s+([a-zA-Z0-9_\-]+)', content)
    if m_st:
        config["spec_type"] = m_st.group(1)

    m_mtp_var = re.search(r'set\s+["\']?MTP_MODEL=(?:%BASEDIR%)?([^"\'\r\n]+)', content, re.IGNORECASE)
    m_sdm = re.search(r'--spec-draft-model\s+["\']?([^"\'\r\n]+)["\']?', content)
    if m_sdm:
        raw_sdm = m_sdm.group(1).replace("%BASEDIR%", "").strip()
        if "%MTP_MODEL%" in raw_sdm.upper() and m_mtp_var:
            config["spec_draft_model"] = Path(m_mtp_var.group(1).strip()).name
        else:
            config["spec_draft_model"] = Path(raw_sdm).name
    elif m_mtp_var and m_st:
        config["spec_draft_model"] = Path(m_mtp_var.group(1).strip()).name

    m_sdn = re.search(r'--spec-draft-n-max\s+(\d+)', content)
    if m_sdn:
        config["spec_draft_n_max"] = int(m_sdn.group(1))

    m_sdp = re.search(r'--spec-draft-p-min\s+([0-9.]+)', content)
    if m_sdp:
        config["spec_draft_p_min"] = float(m_sdp.group(1))

    m_ngld = re.search(r'--n-gpu-layers-draft\s+([a-zA-Z0-9_]+)', content)
    if m_ngld:
        config["n_gpu_layers_draft"] = m_ngld.group(1)

    # Available MTP detection in folder
    available_mtp = config.get("spec_draft_model", "")
    if not available_mtp or not (bat_path.parent / available_mtp).exists():
        available_mtp = ""
        try:
            for f in bat_path.parent.glob("*mtp*.gguf"):
                available_mtp = f.name
                break
            if not available_mtp:
                for f in bat_path.parent.glob("*draft*.gguf"):
                    available_mtp = f.name
                    break
        except Exception:
            pass
    config["available_mtp"] = available_mtp
    config["mtp_enabled"] = bool(config.get("spec_draft_model") and config.get("spec_type"))

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
        # Also update comments or echo with Contexto: ... tokens
        updated = re.sub(r'Contexto:\s*\d+\s*tokens', f'Contexto: {ctx} tokens', updated)

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

    if "engine" in updates and updates["engine"]:
        engine_val = str(updates["engine"]).upper().strip()
        bin_map = {
            "CPU": "llama-b9283-bin-win-cpu-x64",
            "VULKAN": "llama-b9297-bin-win-vulkan-x64",
            "CUDA": "llama-b9297-bin-win-cuda-x64"
        }
        target_bin_folder = bin_map.get(engine_val)
        if target_bin_folder:
            updated = re.sub(
                r'llama-(?:b\d+)?-?bin-win-(?:cuda|vulkan|cpu)-x64',
                target_bin_folder,
                updated
            )

    ck = updates.get("cache_type_k")
    cv = updates.get("cache_type_v")
    if ck is not None:
        ck = str(ck).lower().strip()
    if cv is not None:
        cv = str(cv).lower().strip()
    elif ck is not None:
        cv = ck

    # KV Cache quantization strictly requires Flash Attention in llama.cpp
    if ck and ck not in ("f16", "none"):
        updates["flash_attn"] = True

    if "flash_attn" in updates and updates["flash_attn"] is not None:
        fa_val = "on" if updates["flash_attn"] else "off"
        if re.search(r'--flash-attn\s+(on|off)', updated):
            updated = re.sub(r'--flash-attn\s+(on|off)', f'--flash-attn    {fa_val}', updated)
        elif re.search(r'-fa\s+(on|off)', updated):
            updated = re.sub(r'-fa\s+(on|off)', f'-fa {fa_val}', updated)

    desc_map = {
        "iq4_nl": "Rendimiento (iq4_nl)",
        "q4_0": "Ultra Rendimiento (q4_0)",
        "q5_0": "Equilibrado (q5_0)",
        "q8_0": "Calidad (q8_0)",
        "f16": "FP16 (sin comprimir)",
        "none": "FP16 (sin comprimir)"
    }

    if ck:
        has_k = bool(re.search(r'--cache-type-k\s+[A-Za-z0-9_]+', updated))
        has_v = bool(re.search(r'--cache-type-v\s+[A-Za-z0-9_]+', updated))

        if ck in ("f16", "none"):
            if has_k:
                updated = re.sub(r'--cache-type-k\s+[A-Za-z0-9_]+', '--cache-type-k  f16', updated)
            if has_v:
                updated = re.sub(r'--cache-type-v\s+[A-Za-z0-9_]+', '--cache-type-v  f16', updated)
        else:
            if has_k:
                updated = re.sub(r'--cache-type-k\s+[A-Za-z0-9_]+', f'--cache-type-k  {ck}', updated)
            if has_v:
                updated = re.sub(r'--cache-type-v\s+[A-Za-z0-9_]+', f'--cache-type-v  {cv}', updated)

            if not has_k and not has_v:
                # Insert flags into server invocation block
                m_target = re.search(r'(--ubatch-size\s+\d+\s*\^|--ctx-size\s+\d+\s*\^|--flash-attn\s+(?:on|off)\s*\^)', updated)
                if m_target:
                    insert_lines = f"\r\n  --cache-type-k  {ck}        ^\r\n  --cache-type-v  {cv}        ^"
                    updated = updated[:m_target.end()] + insert_lines + updated[m_target.end():]
                else:
                    m_model = re.search(r'(--model\s+["\'][^"\']+["\']\s*\^|--model\s+\S+\s*\^)', updated)
                    if m_model:
                        insert_lines = f"\r\n  --cache-type-k  {ck}        ^\r\n  --cache-type-v  {cv}        ^"
                        updated = updated[:m_model.end()] + insert_lines + updated[m_model.end():]
            elif has_k and not has_v:
                updated = re.sub(r'(--cache-type-k\s+[A-Za-z0-9_]+\s*\^)', rf'\1\r\n  --cache-type-v  {cv}        ^', updated)
            elif has_v and not has_k:
                updated = re.sub(r'(--cache-type-v\s+[A-Za-z0-9_]+\s*\^)', rf'--cache-type-k  {ck}        ^\r\n  \1', updated)

        # Synchronize header echo banner for KV Cache
        cache_desc = desc_map.get(ck, ck)
        if re.search(r'echo\s+KV Cache\s*:[^\r\n]*\^?\|\s*Contexto:\s*\d+\s*tokens', updated):
            ctx_match = re.search(r'Contexto:\s*(\d+)\s*tokens', updated)
            ctx_tokens = ctx_match.group(1) if ctx_match else "16384"
            if "context" in updates and updates["context"]:
                ctx_tokens = str(updates["context"])
            updated = re.sub(
                r'echo\s+KV Cache\s*:[^\r\n]*\^?\|\s*Contexto:\s*\d+\s*tokens',
                f'echo  KV Cache        : {cache_desc} ^| Contexto: {ctx_tokens} tokens',
                updated
            )
        elif re.search(r'echo\s+KV Cache\s*:.*', updated):
            updated = re.sub(r'echo\s+KV Cache\s*:.*', f'echo  KV Cache        : {cache_desc}', updated)

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

    if "mmproj_file" in updates:
        mmproj = updates["mmproj_file"]
        if mmproj:
            mmproj_name = Path(mmproj).name
            if re.search(r'set\s+["\']?MMPROJ=.*', updated, re.IGNORECASE):
                updated = re.sub(r'set\s+["\']?MMPROJ=[^\r\n]*', f'set "MMPROJ=%BASEDIR%{mmproj_name}"', updated, flags=re.IGNORECASE)
            if re.search(r'set\s+["\']?MMPROJ_FLAG=.*', updated, re.IGNORECASE):
                updated = re.sub(r'set\s+["\']?MMPROJ_FLAG=[^\r\n]*', 'set "MMPROJ_FLAG=--mmproj "!MMPROJ!""', updated, flags=re.IGNORECASE)
        else:
            if re.search(r'set\s+["\']?MMPROJ=.*', updated, re.IGNORECASE):
                updated = re.sub(r'set\s+["\']?MMPROJ=[^\r\n]*', 'set "MMPROJ="', updated, flags=re.IGNORECASE)
            if re.search(r'set\s+["\']?MMPROJ_FLAG=.*', updated, re.IGNORECASE):
                updated = re.sub(r'set\s+["\']?MMPROJ_FLAG=[^\r\n]*', 'set "MMPROJ_FLAG="', updated, flags=re.IGNORECASE)

    # Multi Token Prediction (MTP) Speculative Decoding
    if "spec_draft_model" in updates or "spec_type" in updates or "mtp_enabled" in updates:
        spec_model = updates.get("spec_draft_model", "")
        spec_type = updates.get("spec_type", "draft-mtp" if spec_model else "")
        mtp_enabled = updates.get("mtp_enabled")
        if mtp_enabled is None:
            mtp_enabled = bool(spec_model and spec_type)

        if mtp_enabled and spec_model:
            model_name = Path(spec_model.replace("%BASEDIR%", "").strip()).name
            # If script uses set "MTP_MODEL=..."
            if re.search(r'set\s+["\']?MTP_MODEL=.*', updated, re.IGNORECASE):
                updated = re.sub(r'set\s+["\']?MTP_MODEL=[^\r\n]*', f'set "MTP_MODEL=%BASEDIR%{model_name}"', updated, flags=re.IGNORECASE)

            # Update or insert flags
            if re.search(r'--spec-draft-model\s+["\']?[^"\'\r\n]+["\']?', updated):
                if not re.search(r'--spec-draft-model\s+["\']?%MTP_MODEL%["\']?', updated):
                    updated = re.sub(r'--spec-draft-model\s+["\']?[^"\'\r\n]+["\']?', f'--spec-draft-model    "%BASEDIR%{model_name}"', updated)
            else:
                m_anchor = re.search(r'(!MMPROJ_FLAG!\s*\^|--model\s+["\'][^"\']+["\']\s*\^|--model\s+\S+\s*\^)', updated)
                if m_anchor:
                    n_max = updates.get("spec_draft_n_max", 2)
                    p_min = updates.get("spec_draft_p_min", 0.5)
                    draft_ngl = updates.get("n_gpu_layers_draft", "all")
                    spec_flags = (
                        f"\r\n  --spec-type           {spec_type or 'draft-mtp'}     ^"
                        f"\r\n  --spec-draft-model    \"%BASEDIR%{model_name}\" ^"
                        f"\r\n  --spec-draft-n-max    {n_max}             ^"
                        f"\r\n  --spec-draft-p-min    {p_min}           ^"
                        f"\r\n  --n-gpu-layers-draft  {draft_ngl}           ^"
                    )
                    updated = updated[:m_anchor.end()] + spec_flags + updated[m_anchor.end():]

            if re.search(r'--spec-type\s+[a-zA-Z0-9_\-]+', updated):
                updated = re.sub(r'--spec-type\s+[a-zA-Z0-9_\-]+', f'--spec-type           {spec_type or "draft-mtp"}', updated)

            # Update echo header if present
            if re.search(r'echo\s+Modelo Borrador\s*:.*', updated):
                updated = re.sub(r'echo\s+Modelo Borrador\s*:.*', f'echo  Modelo Borrador : {model_name} (MTP Draft)', updated)
        else:
            # MTP disabled: clear variable and remove inline flags
            if re.search(r'set\s+["\']?MTP_MODEL=.*', updated, re.IGNORECASE):
                updated = re.sub(r'set\s+["\']?MTP_MODEL=[^\r\n]*', 'set "MTP_MODEL="', updated, flags=re.IGNORECASE)

            updated = re.sub(r'\r?\n\s*--spec-type\s+[^\r\n]+\s*\^', '', updated)
            updated = re.sub(r'\r?\n\s*--spec-draft-model\s+[^\r\n]+\s*\^', '', updated)
            updated = re.sub(r'\r?\n\s*--spec-draft-n-max\s+[^\r\n]+\s*\^', '', updated)
            updated = re.sub(r'\r?\n\s*--spec-draft-p-min\s+[^\r\n]+\s*\^', '', updated)
            updated = re.sub(r'\r?\n\s*--n-gpu-layers-draft\s+[^\r\n]+\s*\^', '', updated)

            if re.search(r'echo\s+Modelo Borrador\s*:.*', updated):
                updated = re.sub(r'echo\s+Modelo Borrador\s*:.*', 'echo  Modelo Borrador : Desactivado', updated)

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


def bat_to_json_dict(bat_path: Path) -> Dict[str, Any]:
    """
    Parses a .bat script and converts its configuration into a clean JSON dictionary.
    """
    parsed = parse_batch_script(bat_path)
    if not parsed.get("success", False):
        return parsed

    ngl = parsed.get("ngl", 99)
    engine = "CPU" if ngl == 0 else "CUDA"

    folder = bat_path.parent
    if folder.parent.name and folder.parent.name.lower() != "models":
        name = f"{folder.parent.name} — {folder.name}"
    else:
        name = folder.name

    json_dict: Dict[str, Any] = {
        "name": name,
        "alias": parsed.get("alias", ""),
        "model_file": parsed.get("model_file", ""),
        "mmproj_file": parsed.get("mmproj_file", ""),
        "engine": engine,
        "ngl": ngl,
        "threads": parsed.get("threads", 8),
        "context": parsed.get("context", 8192),
        "ubatch_size": parsed.get("ubatch_size", 512),
        "flash_attn": parsed.get("flash_attn", True if engine != "CPU" else False),
        "cache_type_k": parsed.get("cache_type_k", "q4_0"),
        "cache_type_v": parsed.get("cache_type_v", "q4_0"),
        "temp": parsed.get("temp", 0.7),
        "top_p": parsed.get("top_p", 0.95),
        "top_k": parsed.get("top_k", 40),
        "min_p": parsed.get("min_p", 0.05),
        "repeat_penalty": parsed.get("repeat_penalty", 1.0),
        "host": parsed.get("host", "0.0.0.0"),
        "port": parsed.get("port", 8080),
        "associated_bat": bat_path.name
    }

    spec_draft = parsed.get("spec_draft_model", "")
    if parsed.get("spec_type") or spec_draft:
        json_dict["spec_type"] = parsed.get("spec_type", "draft-mtp")
        json_dict["spec_draft_model"] = spec_draft
        json_dict["spec_draft_n_max"] = parsed.get("spec_draft_n_max", 2)
        json_dict["spec_draft_p_min"] = parsed.get("spec_draft_p_min", 0.5)
        json_dict["n_gpu_layers_draft"] = parsed.get("n_gpu_layers_draft", "all")
    else:
        json_dict["spec_type"] = ""
        json_dict["spec_draft_model"] = ""

    return json_dict


def convert_bat_to_json(bat_path: Path, overwrite: bool = True) -> Dict[str, Any]:
    """
    Converts a single .bat file to a corresponding .json file right next to it.
    """
    json_path = bat_path.with_suffix(".json")
    if json_path.exists() and not overwrite:
        return {"success": True, "json_path": str(json_path), "skipped": True}

    data = bat_to_json_dict(bat_path)
    if not data or (not data.get("model_file") and "error" in data):
        return {"success": False, "error": data.get("error", "Failed to parse batch script")}

    try:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        json_path.write_text(json_str, encoding="utf-8")
        return {"success": True, "json_path": str(json_path), "data": data}
    except Exception as e:
        return {"success": False, "error": f"Failed to write json: {e}"}


def parse_json_config(json_path: Path) -> Dict[str, Any]:
    """
    Parses a model .json configuration file and returns a dictionary compatible
    with frontend expectations.
    """
    if not json_path.exists() or not json_path.is_file():
        return {"success": False, "error": f"JSON config not found: {json_path}"}

    try:
        content = json_path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(content)
    except Exception as e:
        return {"success": False, "error": f"Failed to parse JSON file: {e}"}

    has_backup = json_path.with_suffix(".json.bak").exists()
    associated_bat = json_path.with_suffix(".bat")
    bat_raw = ""
    if associated_bat.exists():
        try:
            bat_raw = associated_bat.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ngl = data.get("ngl", data.get("n_gpu_layers", 99))
    engine = data.get("engine", "CPU" if ngl == 0 else "CUDA")

    mmproj_file = data.get("mmproj_file", "")
    if mmproj_file and not (json_path.parent / mmproj_file).exists():
        mmproj_file = ""

    available_mmproj = mmproj_file
    if not available_mmproj:
        try:
            for f in json_path.parent.glob("*mmproj*.gguf"):
                available_mmproj = f.name
                break
        except Exception:
            pass

    # Resolve Multi Token Prediction (MTP) draft model
    spec_draft_model = data.get("spec_draft_model", "")
    if "%MTP_MODEL%" in spec_draft_model.upper():
        spec_draft_model = ""

    if spec_draft_model and not (json_path.parent / spec_draft_model).exists():
        spec_draft_model = ""

    available_mtp = spec_draft_model
    if not available_mtp and bat_raw:
        m_mtp_var = re.search(r'set\s+["\']?MTP_MODEL=(?:%BASEDIR%)?([^"\'\r\n]+)', bat_raw, re.IGNORECASE)
        if m_mtp_var:
            cand = Path(m_mtp_var.group(1).strip()).name
            if (json_path.parent / cand).exists():
                available_mtp = cand

    if not available_mtp:
        try:
            for f in json_path.parent.glob("*mtp*.gguf"):
                available_mtp = f.name
                break
            if not available_mtp:
                for f in json_path.parent.glob("*draft*.gguf"):
                    available_mtp = f.name
                    break
        except Exception:
            pass

    if data.get("spec_type") and not spec_draft_model and available_mtp:
        spec_draft_model = available_mtp

    mtp_enabled = bool(spec_draft_model and data.get("spec_type"))

    config: Dict[str, Any] = {
        "success": True,
        "config_format": "JSON",
        "path": str(json_path),
        "json_path": str(json_path),
        "bat_path": str(associated_bat) if associated_bat.exists() else None,
        "filename": json_path.name,
        "has_backup": has_backup,
        "raw_content": json.dumps(data, indent=2, ensure_ascii=False),
        "bat_raw_content": bat_raw,
        "port": data.get("port", 8080),
        "host": data.get("host", "0.0.0.0"),
        "threads": data.get("threads", 8),
        "context": data.get("context", data.get("ctx_size", 8192)),
        "ngl": ngl,
        "engine": engine,
        "ubatch_size": data.get("ubatch_size", 512),
        "flash_attn": True if data.get("cache_type_k") not in ("f16", "none", None, "") else data.get("flash_attn", True),
        "cache_type_k": data.get("cache_type_k", "q4_0"),
        "cache_type_v": data.get("cache_type_v", "q4_0"),
        "temp": data.get("temp", 0.7),
        "top_p": data.get("top_p", 0.95),
        "top_k": data.get("top_k", 40),
        "min_p": data.get("min_p", 0.05),
        "repeat_penalty": data.get("repeat_penalty", 1.0),
        "model_file": data.get("model_file", ""),
        "mmproj_file": mmproj_file,
        "available_mmproj": available_mmproj,
        "vision_enabled": bool(mmproj_file),
        "alias": data.get("alias", ""),
        "spec_type": data.get("spec_type", "draft-mtp" if spec_draft_model else ""),
        "spec_draft_model": spec_draft_model,
        "available_mtp": available_mtp,
        "mtp_enabled": mtp_enabled,
        "spec_draft_n_max": data.get("spec_draft_n_max", 2),
        "spec_draft_p_min": data.get("spec_draft_p_min", 0.5),
        "n_gpu_layers_draft": data.get("n_gpu_layers_draft", "all")
    }
    return config


def save_json_config(
    json_path: Path, 
    content_or_dict: Any, 
    create_backup: bool = True, 
    sync_bat: bool = True
) -> Dict[str, Any]:
    """
    Persists configuration to a .json file with optional backup and automatic synchronization
    to the matching .bat file.
    """
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content_or_dict, str):
            data = json.loads(content_or_dict)
        elif isinstance(content_or_dict, dict):
            data = content_or_dict
        else:
            return {"success": False, "error": f"Invalid content type: {type(content_or_dict)}"}

        backup_created = False
        backup_path = json_path.with_suffix(".json.bak")
        if create_backup and json_path.exists():
            shutil.copy2(json_path, backup_path)
            backup_created = True

        formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
        json_path.write_text(formatted_json, encoding="utf-8")

        # Sync to corresponding .bat if requested
        bat_synced = False
        bat_path = json_path.with_suffix(".bat")
        if sync_bat:
            if bat_path.exists():
                try:
                    bat_content = bat_path.read_text(encoding="utf-8", errors="replace")
                    updated_bat = update_batch_script_content(bat_content, data)
                    save_batch_script(bat_path, updated_bat, create_backup=create_backup)
                    bat_synced = True
                except Exception as e:
                    print(f"[WARN] Failed to sync .bat from JSON: {e}")

        return {
            "success": True,
            "path": str(json_path),
            "backup_created": backup_created,
            "backup_path": str(backup_path) if backup_created else None,
            "bat_synced": bat_synced,
            "parsed_config": parse_json_config(json_path)
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to save JSON config: {e}"}


def migrate_all_bats_to_json(models_root: Path) -> List[Dict[str, Any]]:
    """
    Discovers every .bat file under models_root and generates a corresponding .json file.
    """
    results = []
    if not models_root.exists():
        return results

    for bat in models_root.rglob("*.bat"):
        if bat.name.endswith(".bak"):
            continue
        res = convert_bat_to_json(bat, overwrite=True)
        results.append({
            "bat": str(bat),
            "json": str(bat.with_suffix(".json")),
            "success": res.get("success", False),
            "error": res.get("error", None)
        })
    return results

