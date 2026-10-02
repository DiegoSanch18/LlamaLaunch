"""
Model Catalog, Hierarchical Scanner & Downloader Engine
======================================================
Discovers local LLM models in 2-level canonical tree structures (Family / Variant),
classifies weights, multimodal vision projectors (mmproj), speculative drafts (mtp),
identifies dedicated binary forks (llama.cpp/llama-server.exe), and maps batch scripts.
"""

import os
import sys
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Any

# Safe import of binaries module
try:
    from llamaLauncher.app.backend import binaries
except ImportError:
    try:
        from app.backend import binaries
    except ImportError:
        try:
            import binaries  # type: ignore
        except ImportError:
            binaries = None

# Predefined recommended models mapping Hugging Face URLs (Ollama-style Pull library)
RECOMMENDED_MODELS = {
    "1": {
        "name": "Gemma 4 E2B Instruct (Q4_K_M)",
        "category": "edge",
        "filename": "google_gemma-4-E2B-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF/resolve/main/google_gemma-4-E2B-it-Q4_K_M.gguf",
        "size_est": "3.2 GB"
    },
    "2": {
        "name": "Qwen 2.5 Coder 3B Instruct (Q4_K_M)",
        "category": "coder",
        "filename": "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
        "size_est": "2.1 GB"
    },
    "3": {
        "name": "Llama 3 8B Instruct (Q5_K_M)",
        "category": "large",
        "filename": "Meta-Llama-3-8B-Instruct-Q5_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q5_K_M.gguf",
        "size_est": "5.7 GB"
    },
    "4": {
        "name": "Qwen 2.5 Coder 7B Instruct (Q5_K_M)",
        "category": "coder",
        "filename": "Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q5_k_m.gguf",
        "size_est": "5.3 GB"
    }
}

# Directories to ignore during recursive tree scanning
IGNORED_DIR_NAMES = {
    ".cache", ".git", ".github", "llama.cpp", "__pycache__", 
    "venv", ".venv", "build", "dist", "laya"
}


def _classify_gguf_file(filename: str) -> str:
    """
    Classifies a .gguf file into:
    - 'mmproj': Vision / Multimodal Projector (mmproj-*.gguf or *-mmproj*.gguf)
    - 'mtp': Speculative Draft Model (mtp-*.gguf or draft-*.gguf)
    - 'weight': Base LLM Model Weights
    """
    lower = filename.lower()
    if "mmproj" in lower:
        return "mmproj"
    if lower.startswith("mtp-") or "-mtp-" in lower or "-mtp." in lower or "draft" in lower:
        return "mtp"
    return "weight"


def _extract_quantization(filename: str) -> str:
    """Extracts quantization type from filename using regex."""
    m = re.search(
        r'[-_](UD-[A-Za-z0-9_]+|IQ[0-9]_[A-Za-z0-9_]+|PQ[0-9]_[0-9]|PTQ[0-9]_[0-9]|Q[0-9]_[A-Za-z0-9_]+|BF16|FP16)\.gguf$',
        filename,
        re.IGNORECASE
    )
    return m.group(1).upper() if m else "Unknown"


def _parse_directorio_catalog(models_root: Path) -> Dict[str, str]:
    """
    Parses DIRECTORIO.md in models_root (if present) to build a mapping from
    relative file path to human-friendly display name.
    """
    catalog = {}
    doc_path = models_root / "DIRECTORIO.md"
    if not doc_path.exists():
        return catalog

    try:
        content = doc_path.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("|") and not line_str.startswith("| ---") and not line_str.startswith("| Modelo"):
                parts = [p.strip() for p in line_str.split("|")[1:-1]]
                if len(parts) >= 2:
                    name = parts[0]
                    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', parts[1])
                    for _, link in links:
                        decoded = urllib.parse.unquote(link).replace("/", os.sep)
                        catalog[decoded.lower()] = name
    except Exception:
        pass
    return catalog


def _find_server_exe_in_folder(folder: Path) -> Optional[Path]:
    """Locates llama-server executable within a folder cross-platform."""
    exe_names = ["llama-server.exe", "llama-server"] if sys.platform == "win32" else ["llama-server", "llama-server.exe"]
    for name in exe_names:
        cand = folder / name
        if cand.is_file():
            return cand
    return None


def _resolve_dedicated_binary(model_dir: Path, family_dir: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Checks if a dedicated binary (e.g. Bonsai 2 ternary fork) is located in:
    1. model_dir / llama.cpp / llama-server.exe
    2. family_dir / llama.cpp / llama-server.exe
    Returns (has_dedicated_binary, binary_path, binary_dir).
    """
    # Priority 1: In model_dir
    cand1 = model_dir / "llama.cpp"
    if cand1.is_dir():
        exe1 = _find_server_exe_in_folder(cand1)
        if exe1:
            return True, str(exe1), str(cand1)

    # Priority 2: In family_dir
    cand2 = family_dir / "llama.cpp"
    if cand2.is_dir():
        exe2 = _find_server_exe_in_folder(cand2)
        if exe2:
            return True, str(exe2), str(cand2)

    return False, None, None


def _format_model_labels(
    rel_path: Path, 
    weights: List[Dict[str, Any]], 
    catalog: Dict[str, str]
) -> Tuple[str, str, str, str, str]:
    """
    Derives (id, family, variant, concatenated_label, display_name).
    Enforces R3 standard: 'Familia — Subcarpeta/Modelo'.
    """
    parts = rel_path.parts
    family = parts[0]

    # Check if catalog has a known display name for primary weight
    display_name = ""
    if weights:
        primary_rel = str(rel_path / weights[0]["filename"]).lower()
        display_name = catalog.get(primary_rel, "")

    if len(parts) > 1:
        # Multi-level folder (e.g. Gemma 4/12B, Qwen 2.5/Coder/14B)
        raw_variant = " ".join(parts[1:]).replace("_", " ")
        if "DeepSeek-R1-Distill-Qwen-14B" in raw_variant or "DeepSeek R1" in raw_variant:
            variant = "DeepSeek R1 14B"
        else:
            variant = raw_variant
        concatenated_label = f"{family} — {variant}"
    else:
        # Single-level folder (e.g. Bonsai 2, Qwen 3.6 35B, Ornith 1.5, Qwen3.6-27B-Q4_0)
        if family == "Bonsai 2":
            variant = "27B (Ternario)"
            concatenated_label = f"{family} — {variant}"
        elif family == "Qwen3.6-27B-Q4_0":
            family = "Qwen 3.6"
            variant = "27B"
            concatenated_label = f"{family} — {variant}"
        elif family == "Ornith 1.5":
            variant = "35B"
            concatenated_label = f"{family} — {variant}"
        elif " " in family and any(c.isdigit() for c in family.split()[-1]):
            # e.g. "Qwen 3.6 35B" or "MiMo 2.6 9B"
            variant = ""
            concatenated_label = family
        else:
            variant = ""
            concatenated_label = family

    if not display_name:
        display_name = concatenated_label

    # Normalized slug ID (e.g. "gemma-4-12b", "bonsai-2-27b-ternario")
    slug = re.sub(r'[^a-z0-9]+', '-', concatenated_label.lower()).strip('-')

    return slug, family, variant, concatenated_label, display_name


def scan_models_and_batches(models_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Recursively scans models_root up to 3 levels, discovering model units,
    separating base weights, vision projectors (mmproj), MTP drafts, dedicated
    binaries (llama.cpp/llama-server.exe), and batch scripts (*.bat).
    """
    if models_root is None:
        if binaries and hasattr(binaries, "resolve_models_dir"):
            models_root = binaries.resolve_models_dir()
        else:
            g_drive_path = Path("G:/My Drive/AI Local/models")
            if g_drive_path.exists():
                models_root = g_drive_path
            else:
                backend_dir = Path(__file__).resolve().parent
                repo_root = backend_dir.parent.parent.parent
                models_root = repo_root / "models"

    models_root = Path(models_root).resolve()
    if not models_root.exists():
        return {
            "success": False,
            "error": f"Models directory not found: {models_root}",
            "root_dir": str(models_root),
            "total_models": 0,
            "models": [],
            "pending_models": []
        }

    catalog = _parse_directorio_catalog(models_root)
    model_units: List[Dict[str, Any]] = []
    pending_models: List[Dict[str, Any]] = []

    for family_dir in sorted(models_root.iterdir()):
        if not family_dir.is_dir() or family_dir.name.startswith("."):
            continue

        # Check for non-GGUF and empty directory edge cases
        all_ggufs_in_family = [
            f for f in family_dir.rglob("*.gguf") 
            if not any(part.startswith(".") for part in f.parts)
        ]

        if not all_ggufs_in_family:
            safetensors = list(family_dir.rglob("*.safetensors"))
            if safetensors:
                pending_models.append({
                    "name": family_dir.name,
                    "folder_path": str(family_dir),
                    "reason": "Non-GGUF Python model (safetensors)"
                })
            else:
                pending_models.append({
                    "name": family_dir.name,
                    "folder_path": str(family_dir),
                    "reason": "Empty / Pending download (no GGUF weights)"
                })
            continue

        # Find candidate model unit folders (folders directly containing base weights)
        candidate_dirs: List[Path] = []
        possible_dirs = [family_dir] + [
            p for p in family_dir.rglob("*") 
            if p.is_dir() and not any(part in IGNORED_DIR_NAMES or part.startswith(".") for part in p.parts)
        ]

        for d in possible_dirs:
            direct_weights = [
                f for f in d.glob("*.gguf") 
                if _classify_gguf_file(f.name) == "weight" and not f.name.endswith(".incomplete") and not f.name.endswith(".lock")
            ]
            if direct_weights:
                candidate_dirs.append(d)

        for d in candidate_dirs:
            rel = d.relative_to(models_root)

            # 1. Collect & Classify GGUF files in this directory
            weights: List[Dict[str, Any]] = []
            mmproj: List[Dict[str, Any]] = []
            mtp: List[Dict[str, Any]] = []

            for f in sorted(d.glob("*.gguf")):
                if f.name.endswith(".incomplete") or f.name.endswith(".lock"):
                    continue
                file_type = _classify_gguf_file(f.name)
                stat = f.stat()
                mtime_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                entry = {
                    "filename": f.name,
                    "path": str(f),
                    "size_gb": round(stat.st_size / (1024 ** 3), 2),
                    "size_bytes": stat.st_size,
                    "modified_time": mtime_str
                }

                if file_type == "weight":
                    entry["type"] = "model"
                    entry["quantization"] = _extract_quantization(f.name)
                    weights.append(entry)
                elif file_type == "mmproj":
                    mmproj.append(entry)
                elif file_type == "mtp":
                    mtp.append(entry)

            if not weights:
                continue

            # 2. Collect Batch Scripts (*.bat / *.cmd, excluding *.bak)
            batch_scripts: List[Dict[str, Any]] = []
            for b in sorted(d.glob("*.bat")):
                if b.name.endswith(".bak"):
                    continue
                has_bak = b.with_suffix(".bat.bak").exists() or Path(str(b) + ".bak").exists()
                mtime_str = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                batch_scripts.append({
                    "filename": b.name,
                    "path": str(b),
                    "has_backup": has_bak,
                    "last_modified": mtime_str
                })

            # Check family directory for scripts if subfolder has none
            if not batch_scripts and d != family_dir:
                for b in sorted(family_dir.glob("*.bat")):
                    if b.name.endswith(".bak"):
                        continue
                    has_bak = b.with_suffix(".bat.bak").exists() or Path(str(b) + ".bak").exists()
                    mtime_str = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    batch_scripts.append({
                        "filename": b.name,
                        "path": str(b),
                        "has_backup": has_bak,
                        "last_modified": mtime_str
                    })

            default_batch = batch_scripts[0]["filename"] if batch_scripts else None

            # 3. Dedicated Binary Resolution
            has_ded_bin, ded_bin_path, ded_bin_dir = _resolve_dedicated_binary(d, family_dir)

            # 4. Labeling & Identification
            slug, fam, var, label, display_name = _format_model_labels(rel, weights, catalog)

            model_units.append({
                "id": slug,
                "family": fam,
                "variant": var,
                "concatenated_label": label,
                "display_name": display_name,
                "folder_path": str(d),
                "has_dedicated_binary": has_ded_bin,
                "dedicated_binary_path": ded_bin_path,
                "dedicated_binary_dir": ded_bin_dir,
                "weights": weights,
                "mmproj": mmproj,
                "mtp": mtp,
                "batch_scripts": batch_scripts,
                "default_batch": default_batch,
                "last_used": "Never"
            })

    # Sort models by concatenated label
    model_units.sort(key=lambda m: m["concatenated_label"].lower())

    return {
        "success": True,
        "root_dir": str(models_root),
        "total_models": len(model_units),
        "models": model_units,
        "pending_models": pending_models
    }


def scan_local_models(models_dir: Path, category: str) -> List[Tuple[str, Path]]:
    """
    Scans a specific category folder for .gguf models (legacy compatibility).
    Returns a list of tuples: (filename, absolute_path).
    """
    category_dir = models_dir / category
    if not category_dir.exists():
        return []
    
    gguf_files = []
    for f in category_dir.glob("*.gguf"):
        gguf_files.append((f.name, f))
    return sorted(gguf_files)


def download_model_core(url: str, target_path: Path, progress_callback: Callable[[Dict], None]) -> bool:
    """
    Downloads a GGUF model from Hugging Face or direct URL with progress updates.
    Returns True on success, False on failure.
    Runs non-blockingly if launched in a Python thread.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Setup temporary file path to prevent locking / corruption on partial downloads
    temp_path = target_path.with_suffix(".download")
    
    if temp_path.exists():
        temp_path.unlink()
        
    start_time = time.time()
    
    try:
        # Request headers to simulate browser and avoid Hugging Face blocks
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        
        # Open URL connection
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 1024 * 128  # 128 KB buffer
            
            with open(temp_path, "wb") as out_file:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    out_file.write(buffer)
                    downloaded += len(buffer)
                    
                    # Calculate stats
                    duration = time.time() - start_time
                    speed = downloaded / (1024 * 1024 * duration) if duration > 0 else 0
                    percent = min(100, int(downloaded * 100 / total_size)) if total_size > 0 else 0
                    
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    
                    progress_callback({
                        "status": "downloading",
                        "percent": percent,
                        "speed": round(speed, 2),
                        "downloaded_mb": round(downloaded_mb, 1),
                        "total_mb": round(total_mb, 1),
                        "time_elapsed": int(duration)
                    })
            
        # Success: Rename temp file to target GGUF
        if target_path.exists():
            target_path.unlink()
        temp_path.rename(target_path)
        
        progress_callback({
            "status": "completed",
            "percent": 100,
            "speed": 0,
            "downloaded_mb": round(total_size / (1024 * 1024), 1) if total_size > 0 else 0,
            "total_mb": round(total_size / (1024 * 1024), 1) if total_size > 0 else 0,
            "time_elapsed": int(time.time() - start_time)
        })
        return True
        
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        
        progress_callback({
            "status": "error",
            "percent": 0,
            "speed": 0,
            "downloaded_mb": 0,
            "total_mb": 0,
            "time_elapsed": 0,
            "error_msg": str(e)
        })
        return False
