"""
Universal Binary Resolver and Dynamic Path Resolution Engine for LlamaLaunch.
=============================================================================
Governs:
- Dynamic discovery of models_dir and bin_root with fallback logic (F2)
- Detection of dedicated model/family binaries (Priority 1 & 2) (F4)
- Discovery, integer-based sorting, and hardware-aware fallback for generic engines (F5)
- Automated verification and synchronization of CUDA acceleration DLLs on Windows
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Import hardware module safely (supporting both package and standalone imports)
try:
    from llamaLauncher.app.backend import hardware
except ImportError:
    try:
        from app.backend import hardware
    except ImportError:
        import hardware  # type: ignore

# Standard executable name per platform
SERVER_EXE_NAME = "llama-server.exe" if sys.platform == "win32" else "llama-server"

# Canonical regex for generic build directory names
# Example: llama-b9297-bin-win-cuda-x64 or llama-b11368-bin-win-cuda-13.1-x64
GENERIC_BUILD_REGEX = re.compile(
    r"llama-(?:b(?P<build>\d+))?-?bin-(?P<os>[a-zA-Z0-9]+)-(?P<backend>[a-zA-Z0-9]+)(?:-[a-zA-Z0-9.]+)?-(?P<arch>[a-zA-Z0-9]+)",
    re.IGNORECASE
)


def _find_server_exe(folder: Path) -> Optional[Path]:
    """Helper to locate llama-server executable within a folder cross-platform."""
    candidates = [folder / SERVER_EXE_NAME]
    if SERVER_EXE_NAME != "llama-server.exe":
        candidates.append(folder / "llama-server.exe")
    if SERVER_EXE_NAME != "llama-server":
        candidates.append(folder / "llama-server")
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def resolve_project_root() -> Path:
    """
    Resolves the base project root directory.
    Handles compiled standalone executable (PyInstaller) and standard repository structures.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # binaries.py is in llamaLauncher/app/backend/binaries.py
    # parents: [0]=backend, [1]=app, [2]=llamaLauncher, [3]=project_root (LlamaLaunch)
    current_file = Path(__file__).resolve()
    if len(current_file.parents) >= 4:
        return current_file.parents[3]
    return current_file.parent


def resolve_models_dir(project_root: Optional[Path] = None) -> Path:
    """
    Dynamically resolves the models library directory.
    Priority 1: Environment variable LLAMALAUNCH_MODELS_DIR or AI_LOCAL_MODELS_DIR (if set and exists)
    Priority 2: G:\\My Drive\\AI Local\\models (primary ecosystem repository)
    Priority 3: project_root / "models" (local fallback)
    """
    # 1. Check environment variables
    env_path = os.environ.get("LLAMALAUNCH_MODELS_DIR") or os.environ.get("AI_LOCAL_MODELS_DIR")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    # 2. Check canonical external path
    primary_gdrive = Path(r"G:\My Drive\AI Local\models")
    if primary_gdrive.exists() and primary_gdrive.is_dir():
        return primary_gdrive

    # 3. Fallback to project root / models
    root = project_root or resolve_project_root()
    return root / "models"


def resolve_bin_root(project_root: Optional[Path] = None) -> Path:
    """
    Dynamically resolves the generic llama.cpp binary engines root directory.
    Priority 1: Environment variable LLAMALAUNCH_BIN_ROOT or AI_LOCAL_BIN_ROOT (if set and exists)
    Priority 2: G:\\My Drive\\AI Local\\llamaLauncher\\bin\\llama.cpp (primary engines repository)
    Priority 3: project_root / "llamaLauncher" / "bin" / "llama.cpp" (local fallback)
    """
    # 1. Check environment variables
    env_path = os.environ.get("LLAMALAUNCH_BIN_ROOT") or os.environ.get("AI_LOCAL_BIN_ROOT")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    # 2. Check canonical external path
    primary_gdrive = Path(r"G:\My Drive\AI Local\llamaLauncher\bin\llama.cpp")
    if primary_gdrive.exists() and primary_gdrive.is_dir():
        return primary_gdrive

    # 3. Fallback to project root / llamaLauncher / bin / llama.cpp
    root = project_root or resolve_project_root()
    return root / "llamaLauncher" / "bin" / "llama.cpp"


def find_dedicated_binary(model_folder: Optional[Union[str, Path]]) -> Optional[Path]:
    """
    Searches for a dedicated llama-server binary for the specified model folder.
    Priority 1: <model_folder>/llama.cpp/llama-server.exe
    Priority 2: <family_folder>/llama.cpp/llama-server.exe (up to 2 levels up)
    
    Returns absolute Path to the executable if found, or None.
    """
    if not model_folder:
        return None

    folder = Path(model_folder).resolve()
    if not folder.exists() or not folder.is_dir():
        return None

    # Priority 1: Direct model folder dedicated binary
    cand1 = folder / "llama.cpp"
    if cand1.is_dir():
        exe1 = _find_server_exe(cand1)
        if exe1:
            return exe1

    # Priority 2: Family parent folders (up to 2 levels up, e.g. Gemma 4/12B -> Gemma 4)
    current = folder.parent
    for _ in range(2):
        if not current or current == current.parent:
            break
        # Guard against checking 'models' root or filesystem root
        if current.name.lower() in ("models", "") or current.parent == current:
            break
        cand2 = current / "llama.cpp"
        if cand2.is_dir():
            exe2 = _find_server_exe(cand2)
            if exe2:
                return exe2
        current = current.parent

    return None


def scan_generic_binaries(bin_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """
    Scans bin_root for all generic precompiled llama-server engines.
    Extracts build numbers (e.g. b9297 -> 9297) and hardware backends (CUDA, VULKAN, CPU).
    Sorts descending by integer build number.
    
    Returns list of parsed binary descriptors.
    """
    resolved_root = Path(bin_root).resolve() if bin_root else resolve_bin_root()
    if not resolved_root.exists() or not resolved_root.is_dir():
        return []

    binaries = []
    for item in resolved_root.iterdir():
        if not item.is_dir():
            continue

        exe_path = _find_server_exe(item)
        if not exe_path:
            continue

        folder_name = item.name
        build_num = 0
        backend = "GENERIC"

        # 1. Try canonical regex match
        m = GENERIC_BUILD_REGEX.match(folder_name)
        if m:
            build_str = m.group("build")
            build_num = int(build_str) if build_str else 0
            backend = m.group("backend").upper()
        else:
            # 2. Fallback heuristic extraction
            bm = re.search(r"b(\d+)", folder_name, re.IGNORECASE)
            if bm:
                build_num = int(bm.group(1))

            name_lower = folder_name.lower()
            if "cuda" in name_lower:
                backend = "CUDA"
            elif "vulkan" in name_lower:
                backend = "VULKAN"
            elif "cpu" in name_lower or "avx" in name_lower:
                backend = "CPU"

        binaries.append({
            "name": folder_name,
            "dir_path": item,
            "exe_path": exe_path,
            "build": f"b{build_num}" if build_num > 0 else "unknown",
            "build_num": build_num,
            "binary_type": backend,
            "is_dedicated": False
        })

    # Sort descending by integer build number (b9297 before b9283; handles b10000+ properly)
    binaries.sort(key=lambda x: x["build_num"], reverse=True)
    return binaries


def resolve_model_binary(
    model_folder: Optional[Union[str, Path]] = None,
    bin_root: Optional[Union[str, Path]] = None,
    dev_type: str = "CUDA",
    force_generic: bool = False
) -> Dict[str, Any]:
    """
    Universal binary resolution function.
    
    Hierarchy:
    1. Priority 1 & 2: Dedicated binary in model or family folder (unless force_generic=True).
    2. Priority 3: Latest generic precompiled engine in bin_root matching hardware preference.
       - If dev_type is "CUDA": prefers CUDA > VULKAN > CPU.
       - If dev_type is "VULKAN": prefers VULKAN > CPU.
       - If dev_type is "CPU": prefers CPU.
       - If dev_type is "AUTO": detects GPUs via hardware module.
    3. Windows CUDA DLL sync: invokes hardware.check_and_copy_cuda_dlls when CUDA selected.
    
    Returns structured resolution dictionary.
    """
    try:
        resolved_bin_root = Path(bin_root).resolve() if bin_root else resolve_bin_root()
        target_folder = Path(model_folder).resolve() if model_folder else None

        # -------------------------------------------------------------
        # 1. Check Dedicated Binary (Priority 1 & 2)
        # -------------------------------------------------------------
        if not force_generic and target_folder:
            dedicated_exe = find_dedicated_binary(target_folder)
            if dedicated_exe:
                dedicated_dir = dedicated_exe.parent
                ded_build_num = 0
                bm = re.search(r"b(\d+)", str(dedicated_exe), re.IGNORECASE)
                if bm:
                    ded_build_num = int(bm.group(1))
                return {
                    "success": True,
                    "binary_path": str(dedicated_exe),
                    "binary_dir": str(dedicated_dir),
                    "binary_type": "CUSTOM_DEDICATED",
                    "is_dedicated": True,
                    "build": f"b{ded_build_num}" if ded_build_num > 0 else "dedicated",
                    "build_num": ded_build_num,
                    "name": f"{target_folder.name} Dedicated Binary",
                    "cuda_dlls_verified": True,
                    "error": None
                }

        # -------------------------------------------------------------
        # 2. Generic Engine Fallback (Priority 3)
        # -------------------------------------------------------------
        generic_bins = scan_generic_binaries(resolved_bin_root)
        if not generic_bins:
            return {
                "success": False,
                "binary_path": None,
                "binary_dir": None,
                "binary_type": "NONE",
                "is_dedicated": False,
                "build": "none",
                "build_num": 0,
                "name": "None",
                "cuda_dlls_verified": False,
                "error": f"No valid generic llama-server engines found in: {resolved_bin_root}"
            }

        # Establish backend preferences
        dev_upper = (dev_type or "AUTO").upper().strip()
        if dev_upper == "CUDA":
            preferences = ["CUDA", "VULKAN", "CPU"]
        elif dev_upper == "VULKAN":
            preferences = ["VULKAN", "CPU"]
        elif dev_upper == "CPU":
            preferences = ["CPU"]
        else:
            # AUTO hardware detection
            try:
                has_nvidia, has_vulkan = hardware.detect_gpus()
            except Exception:
                has_nvidia, has_vulkan = (False, False)

            if has_nvidia:
                preferences = ["CUDA", "VULKAN", "CPU"]
            elif has_vulkan:
                preferences = ["VULKAN", "CPU"]
            else:
                preferences = ["CPU"]

        # Find best matching generic engine (already sorted descending by build_num)
        selected = None
        for pref in preferences:
            for b in generic_bins:
                if b["binary_type"] == pref:
                    selected = b
                    break
            if selected:
                break

        # Final fallback: take highest build regardless of backend if none matched preference
        if not selected:
            selected = generic_bins[0]

        # -------------------------------------------------------------
        # 3. Windows CUDA DLL Verification
        # -------------------------------------------------------------
        dlls_verified = True
        if selected["binary_type"] == "CUDA" and sys.platform == "win32":
            try:
                dlls_verified = hardware.check_and_copy_cuda_dlls(
                    bin_dir=selected["dir_path"],
                    bin_root=resolved_bin_root
                )
            except Exception:
                dlls_verified = False

        build_num = selected.get("build_num", 0)
        if not build_num:
            folder_name = selected.get("name", "") or selected["dir_path"].name
            m = GENERIC_BUILD_REGEX.match(folder_name)
            if m and m.group("build"):
                build_num = int(m.group("build"))
            else:
                bm = re.search(r"b(\d+)", folder_name, re.IGNORECASE)
                if bm:
                    build_num = int(bm.group(1))

        return {
            "success": True,
            "binary_path": str(selected["exe_path"]),
            "binary_dir": str(selected["dir_path"]),
            "binary_type": selected["binary_type"],
            "is_dedicated": False,
            "build": selected["build"],
            "build_num": build_num,
            "name": selected["name"],
            "cuda_dlls_verified": dlls_verified,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "binary_path": None,
            "binary_dir": None,
            "binary_type": "NONE",
            "is_dedicated": False,
            "build": "none",
            "build_num": 0,
            "name": "None",
            "cuda_dlls_verified": False,
            "error": f"Binary resolution error: {str(e)}"
        }
