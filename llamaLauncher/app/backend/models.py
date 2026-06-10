import os
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict
import urllib.request

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

def scan_local_models(models_dir: Path, category: str) -> List[Tuple[str, Path]]:
    """
    Scans a specific category folder for .gguf models.
    Returns a list of tuples: (filename, absolute_path).
    """
    category_dir = models_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)
    
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
