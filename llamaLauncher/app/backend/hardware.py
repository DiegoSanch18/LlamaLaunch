import os
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Tuple

# Timeout in seconds for hardware detection subprocess calls.
# Short timeout prevents freezing the pywebview UI bridge.
_SUBPROCESS_TIMEOUT = 5

def get_cpu_cores() -> Tuple[int, int]:
    """
    Detects physical and logical CPU cores in Windows and Unix without third-party libraries.
    Returns (physical_cores, logical_cores).
    Uses PowerShell on Windows (wmic is deprecated and hangs on Win11).
    """
    logical = os.cpu_count() or 4
    physical = logical
    
    if sys.platform == "win32":
        # Method 1: PowerShell (fast, works on Win10/11)
        try:
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"],
                stderr=subprocess.DEVNULL,
                timeout=_SUBPROCESS_TIMEOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode("utf-8").strip()
            cores = int(output)
            if cores > 0:
                physical = cores
        except Exception:
            # Method 2: Environment variable fallback (instant)
            try:
                env_cores = int(os.environ.get("NUMBER_OF_PROCESSORS", "0"))
                if env_cores > 0:
                    # Estimate physical as half of logical (HyperThreading)
                    physical = max(1, env_cores // 2)
            except (ValueError, TypeError):
                physical = max(1, logical // 2)
    else:
        # Unix/macOS fallback core count
        try:
            if sys.platform == "darwin":
                output = subprocess.check_output(
                    ["sysctl", "-n", "hw.physicalcpu"],
                    timeout=_SUBPROCESS_TIMEOUT
                ).decode("utf-8")
                physical = int(output.strip())
            else:
                output = subprocess.check_output(
                    "lscpu -p=Core | grep -v '^#' | sort -u | wc -l",
                    shell=True,
                    timeout=_SUBPROCESS_TIMEOUT
                ).decode("utf-8")
                physical = int(output.strip())
        except Exception:
            physical = max(1, logical // 2)
            
    return physical, logical

def detect_gpus() -> Tuple[bool, bool]:
    """
    Detects GPU support.
    Returns (has_nvidia, has_vulkan).
    Uses fast file-existence checks first, then subprocess as fallback.
    """
    has_nvidia = False
    has_vulkan = False
    
    # 1. Check for NVIDIA — first try quick file existence check
    nvidia_smi_path = shutil.which("nvidia-smi")
    if nvidia_smi_path:
        try:
            subprocess.check_output(
                "nvidia-smi", 
                shell=True, 
                stderr=subprocess.DEVNULL,
                timeout=_SUBPROCESS_TIMEOUT
            )
            has_nvidia = True
        except Exception:
            # nvidia-smi exists but failed — driver might be busy, still assume NVIDIA present
            has_nvidia = True

    if sys.platform == "win32":
        try:
            # Use PowerShell instead of deprecated wmic
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name -join ','"],
                stderr=subprocess.DEVNULL,
                timeout=_SUBPROCESS_TIMEOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode("utf-8")
            gpu_names = output.lower()
            if "nvidia" in gpu_names:
                has_nvidia = True
            if "amd" in gpu_names or "radeon" in gpu_names or "intel" in gpu_names or has_nvidia:
                has_vulkan = True  # Vulkan supports modern GPUs
        except Exception:
            has_vulkan = has_nvidia
    else:
        # Unix-like GPU check
        has_vulkan = has_nvidia
        try:
            # Simple check if vulkan-info is present
            subprocess.check_output(
                "which vulkaninfo",
                shell=True,
                stderr=subprocess.DEVNULL,
                timeout=_SUBPROCESS_TIMEOUT
            )
            has_vulkan = True
        except Exception:
            pass

    return has_nvidia, has_vulkan

def check_and_copy_cuda_dlls(bin_dir: Path, bin_root: Path, log_callback=None) -> bool:
    """
    Checks if CUDA DLLs are missing in the target llama-server directory.
    If missing, copies them automatically and silently from the runtime cudart directory.
    Returns True if DLLs are verified or copied successfully, False otherwise.
    """
    if sys.platform != "win32":
        return True # DLL copy is Windows-specific
        
    missing = False
    # Check for cublas or cudart DLLs
    has_cublas = list(bin_dir.glob("cublas64_*.dll"))
    has_cublas_lt = list(bin_dir.glob("cublasLt64_*.dll"))
    
    if not has_cublas or not has_cublas_lt:
        missing = True

    if not missing:
        return True

    # DLLs are missing, search for source cudart directory
    source_dir = bin_root / "cudart-llama-bin-win-cuda-13.1-x64"
    if not source_dir.exists():
        msg = f"[WARN] CUDA runtime source folder not found at: {source_dir}"
        if log_callback:
            log_callback(msg)
        else:
            print(msg, file=sys.stderr)
        return False

    msg = f"[INFO] Automatically copying CUDA acceleration DLLs from {source_dir.name} to {bin_dir.name}..."
    if log_callback:
        log_callback(msg)
    else:
        print(msg)

    try:
        copied_count = 0
        for dll_file in source_dir.glob("*.dll"):
            shutil.copy2(dll_file, bin_dir)
            copied_count += 1
        msg = f"[SUCCESS] Automatically copied {copied_count} CUDA DLL files."
        if log_callback:
            log_callback(msg)
        else:
            print(msg)
        return True
    except Exception as e:
        msg = f"[ERROR] Failed to copy DLLs: {e}"
        if log_callback:
            log_callback(msg)
        else:
            print(msg, file=sys.stderr)
        return False
