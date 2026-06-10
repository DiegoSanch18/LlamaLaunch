import os
import sys
import json
import re
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from llamaLauncher.app.backend.manager import ProcessManager
import llamaLauncher.app.backend.hardware as hardware
import llamaLauncher.app.backend.config as config
import llamaLauncher.app.backend.models as models

class ApiBridge:
    """
    Facade / API Bridge class exposed to the pywebview Frontend (JS).
    Encapsulates all process details, file systems, and threads.
    """
    def __init__(self, project_root=None):
        self.manager = ProcessManager()
        self._window = None
        
        # Setup paths — critical for both dev and compiled .exe modes
        if project_root:
            self.project_root = Path(project_root)
        elif getattr(sys, 'frozen', False):
            # Running as compiled .exe — use exe's directory as project root
            self.project_root = Path(sys.executable).resolve().parent
        else:
            # Running as Python script
            self.backend_dir = Path(__file__).resolve().parent
            # backend_dir = project_root/llamaLauncher/app/backend
            self.project_root = self.backend_dir.parent.parent.parent
        
        self.models_dir = self.project_root / "models"
        self.bin_root = self.project_root / "llamaLauncher" / "bin" / "llama.cpp"
        self.logs_dir = self.project_root / "llamaLauncher" / "logs"
        self.history_file = self.logs_dir / "history.json"
        
        # Ensure directories exist
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            self.bin_root.mkdir(parents=True, exist_ok=True)
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[WARN] Could not create directories: {e}")
            
    def _record_model_usage(self, filename: str):
        """Records the timestamp when a model was last loaded."""
        history = {}
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
        except Exception:
            pass
            
        history[filename] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"[WARN] Could not write history.json: {e}")

    def get_hardware_info(self) -> Dict[str, Any]:
        """
        Scans physical/logical cores and GPU acceleration support.
        """
        physical, logical = hardware.get_cpu_cores()
        has_nvidia, has_vulkan = hardware.detect_gpus()
        
        return {
            "physical_cores": physical,
            "logical_cores": logical,
            "has_nvidia": has_nvidia,
            "has_vulkan": has_vulkan,
            "platform": sys.platform
        }

    def scan_models(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Scans and lists available local GGUF models in subdirectories.
        """
        categories = ["edge", "large", "coder"]
        results = {}
        
        history = {}
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
        except Exception:
            pass
        
        param_pattern = re.compile(r'(\d+(?:\.\d+)?[BbMm])', re.IGNORECASE)
        
        for cat in categories:
            results[cat] = []
            gguf_files = models.scan_local_models(self.models_dir, cat)
            for name, path in gguf_files:
                # Size
                try:
                    size_bytes = path.stat().st_size
                    size_gb = round(size_bytes / (1024 * 1024 * 1024), 2)
                except Exception:
                    size_gb = 0
                    
                # Download Date
                try:
                    mtime = path.stat().st_mtime
                    download_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    download_date = "Unknown"
                    
                # Parameter count
                match = param_pattern.search(name)
                parameters = match.group(1).upper() if match else "Unknown"
                
                # Last Used
                last_used = history.get(name, "Never")
                    
                results[cat].append({
                    "filename": name,
                    "absolute_path": str(path),
                    "size_gb": size_gb,
                    "parameters": parameters,
                    "download_date": download_date,
                    "last_used": last_used
                })
        return results

    def delete_local_model(self, category: str, filename: str) -> Dict[str, Any]:
        """
        Permanently deletes a downloaded local GGUF model file.
        Prevents deletion if the model is currently active in the inference server.
        """
        if not filename:
            return {"success": False, "message": "Filename not provided."}
            
        target_path = self.models_dir / category / filename
        if not target_path.exists():
            return {"success": False, "message": f"Model file not found: {filename}"}
            
        # Safety Check: Is it currently loaded in the active llama-server?
        active_info = self.manager.get_status_info()
        if active_info.get("status") in ("LOADING", "RUNNING") and active_info.get("model") == filename:
            return {
                "success": False, 
                "message": "Cannot delete this model because it is currently loaded and running in the active inference server. Please stop the server first."
            }
            
        try:
            target_path.unlink()
            return {"success": True, "message": f"Model '{filename}' deleted successfully."}
        except Exception as e:
            return {"success": False, "message": f"Failed to delete model file: {str(e)}"}

    def get_recommended_models(self) -> Dict[str, Any]:
        """
        Returns recommended models pre-mapping.
        """
        return models.RECOMMENDED_MODELS

    def get_optimized_params(self, engine: str, pq_choice: str) -> Dict[str, Any]:
        """
        Calculates suggested threads, context, and offloaded layers.
        """
        physical, _ = hardware.get_cpu_cores()
        optimized = config.optimize_params(engine, physical, pq_choice)
        return optimized

    def start_server(self, ui_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares environment and launches llama-server from UI arguments.
        """
        try:
            engine = ui_config.get("engine", "CPU")
            model_path_str = ui_config.get("model_path", "")
            port = int(ui_config.get("port", 8080))
            threads = int(ui_config.get("threads", 4))
            context = int(ui_config.get("context", 4096))
            ngl = int(ui_config.get("ngl", 0))
            pq_choice = ui_config.get("pq_choice", "3") # "3" is off
            context_shift = bool(ui_config.get("context_shift", True))

            if not model_path_str:
                return {"success": False, "message": "No model file was selected."}

            model_path = Path(model_path_str)
            if not model_path.exists():
                return {"success": False, "message": f"Model file does not exist: {model_path}"}

            # 1. Resolve Engine Binary Path
            dev_type_lower = engine.lower()
            bin_dir = None
            
            # Scan modern directories like bin/llama.cpp/llama-*-bin-win-cpu-x64
            for folder in self.bin_root.glob(f"llama-*-bin-win-{dev_type_lower}-x64"):
                exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
                if (folder / exe_name).exists():
                    bin_dir = folder
                    break
            
            # Windows fallback scans
            if not bin_dir and sys.platform == "win32":
                for folder in self.bin_root.iterdir():
                    if folder.is_dir() and engine in folder.name.upper():
                        if "CUDART" not in folder.name.upper() and (folder / "llama-server.exe").exists():
                            bin_dir = folder
                            break
            
            # Ultimate default bin folder
            if not bin_dir:
                if sys.platform == "win32":
                    bin_dir = self.bin_root / f"llama-b9283-bin-win-{dev_type_lower}-x64"
                else:
                    # Unix standard search or fallback
                    bin_dir = self.bin_root

            # 2. DLL Check for CUDA acceleration
            if engine == "CUDA" and sys.platform == "win32":
                hardware.check_and_copy_cuda_dlls(bin_dir, self.bin_root)

            # 3. Resolve PolarQuant Flags
            polar_flags, _ = config.get_polar_quant_flags(pq_choice)

            res = self.manager.start_server(
                bin_dir=bin_dir,
                model_path=model_path,
                port=port,
                threads=threads,
                context=context,
                ngl=ngl,
                polar_flags=polar_flags,
                logs_dir=self.logs_dir,
                context_shift=context_shift
            )
            
            if res.get("success"):
                self._record_model_usage(model_path.name)
                
            return res

        except Exception as e:
            return {"success": False, "message": f"API Bridge error: {str(e)}"}

    def stop_server(self) -> Dict[str, Any]:
        """
        Stops the active llama-server process.
        """
        return self.manager.stop_server()

    def get_server_status(self) -> Dict[str, Any]:
        """
        Polls server status and reads last active logs.
        """
        info = self.manager.get_status_info()
        info["logs"] = self.manager.get_recent_logs(25)
        return info

    def set_window(self, window):
        """Sets the active pywebview window reference."""
        self._window = window

    def descargar_modelo(self, url: str, nombre_destino: str, categoria: str = "edge") -> Dict[str, Any]:
        """
        Exposed API method to download a GGUF model asynchronously.
        Delegates task to DownloadManager with requests stream=True.
        """
        if not url:
            return {"success": False, "message": "Download URL not provided."}
            
        filename = nombre_destino or url.split("/")[-1]
        if not filename.endswith(".gguf"):
            filename += ".gguf"
            
        target_path = self.models_dir / categoria / filename
        
        from llamaLauncher.app.backend.manager import DownloadManager
        dm = DownloadManager()
        return dm.start_download(url, target_path, categoria, self._window)

    def cancelar_descarga(self, nombre_destino: str, categoria: str = "edge") -> Dict[str, Any]:
        """
        Exposed API method to cancel an active GGUF download and clean up part files.
        """
        filename = nombre_destino
        if not filename.endswith(".gguf"):
            filename += ".gguf"
        target_path_str = str(self.models_dir / categoria / filename)
        
        from llamaLauncher.app.backend.manager import DownloadManager
        dm = DownloadManager()
        success = dm.cancel_download(target_path_str)
        if success:
            return {"success": True, "message": "Download cancellation requested."}
        return {"success": False, "message": "No active download found for this model."}

    def start_download(self, model_key: str, custom_url: str = "", custom_filename: str = "", category: str = "edge") -> Dict[str, Any]:
        """
        Wrapper to keep recommended models single-click downloads operational.
        """
        url = ""
        filename = ""
        
        if model_key in models.RECOMMENDED_MODELS:
            item = models.RECOMMENDED_MODELS[model_key]
            url = item["url"]
            filename = item["filename"]
            category = item["category"]
        else:
            url = custom_url
            filename = custom_filename or url.split("/")[-1]
            
        return self.descargar_modelo(url, filename, category)

    def search_hf_models(self, query: str) -> Dict[str, Any]:
        """
        Queries Hugging Face API for GGUF models matching search query.
        """
        import requests
        if not query:
            return {"success": False, "message": "Query cannot be empty."}
            
        try:
            url = f"https://huggingface.co/api/models?search={query}&filter=gguf&limit=12&sort=downloads&direction=-1"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            models_data = response.json()
            
            results = []
            for item in models_data:
                results.append({
                    "id": item.get("id"),
                    "downloads": item.get("downloads", 0),
                    "likes": item.get("likes", 0),
                    "tags": item.get("tags", [])
                })
            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "message": f"Hugging Face Search error: {str(e)}"}

    def get_hf_model_files(self, model_id: str) -> Dict[str, Any]:
        """
        Queries Hugging Face API to list sibling GGUF files in a repository.
        """
        import requests
        if not model_id:
            return {"success": False, "message": "Model ID cannot be empty."}
            
        try:
            url = f"https://huggingface.co/api/models/{model_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            siblings = data.get("siblings", [])
            gguf_files = []
            for s in siblings:
                # Hugging Face API lists repository paths using the 'rfilename' key (or 'rpath' as fallback)
                name = s.get("rfilename") or s.get("rpath")
                if name and name.endswith(".gguf"):
                    gguf_files.append(name)
            
            # Sort files alphabetically
            gguf_files.sort()
            
            return {"success": True, "files": gguf_files}
        except Exception as e:
            return {"success": False, "message": f"Failed to list model files: {str(e)}"}

    def open_folder(self, folder_type: str) -> Dict[str, Any]:
        """
        Cross-platform helper to open directories in system explorer.
        """
        path = self.models_dir
        if folder_type == "logs":
            path = self.logs_dir

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            else:
                subprocess.run(["xdg-open", str(path)])
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
