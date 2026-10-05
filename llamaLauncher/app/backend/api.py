import os
import sys
import json
import re
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from llamaLauncher.app.backend.manager import ProcessManager
    import llamaLauncher.app.backend.hardware as hardware
    import llamaLauncher.app.backend.config as config
    import llamaLauncher.app.backend.models as models
    import llamaLauncher.app.backend.binaries as binaries
    import llamaLauncher.app.backend.batch_manager as batch_manager
except ImportError:
    try:
        from app.backend.manager import ProcessManager
        import app.backend.hardware as hardware
        import app.backend.config as config
        import app.backend.models as models
        import app.backend.binaries as binaries
        import app.backend.batch_manager as batch_manager
    except ImportError:
        from manager import ProcessManager  # type: ignore
        import hardware  # type: ignore
        import config  # type: ignore
        import models  # type: ignore
        import binaries  # type: ignore
        import batch_manager  # type: ignore

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
        
        # Dynamic root resolution (Priority to external G:\My Drive\, fallback to local repo)
        self.models_dir = binaries.resolve_models_dir(self.project_root)
        self.bin_root = binaries.resolve_bin_root(self.project_root)
        self.logs_dir = self.project_root / "llamaLauncher" / "logs"
        self.history_file = self.logs_dir / "history.json"
        
        # Ensure directories exist
        try:
            if not self.models_dir.exists():
                self.models_dir.mkdir(parents=True, exist_ok=True)
            if not self.bin_root.exists():
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

    def scan_models_and_batches(self) -> Dict[str, Any]:
        """
        Exposed API method for the Frontend Combobox (R1 & R3).
        Returns hierarchically grouped models, weights, vision projectors,
        speculative drafts, dedicated binary indicators, and batch scripts.
        """
        try:
            res = models.scan_models_and_batches(self.models_dir)
            if not res.get("success"):
                return res

            # Enrich models with last_used timestamp from history.json
            history = {}
            if self.history_file.exists():
                try:
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except Exception:
                    pass

            for m in res.get("models", []):
                # Check history using model id or primary weight filename
                if m.get("weights"):
                    primary_file = m["weights"][0]["filename"]
                    m["last_used"] = history.get(primary_file, history.get(m["id"], "Never"))

            return res
        except Exception as e:
            return {
                "success": False,
                "error": f"Error scanning models and batches: {str(e)}",
                "root_dir": str(self.models_dir),
                "total_models": 0,
                "models": [],
                "pending_models": []
            }

    def resolve_model_binary(self, folder_path: str = "", dev_type: str = "CUDA") -> Dict[str, Any]:
        """
        Pywebview bridge endpoint to resolve binary for a given model folder.
        """
        model_folder = Path(folder_path) if folder_path else None
        return binaries.resolve_model_binary(
            model_folder=model_folder,
            bin_root=self.bin_root,
            dev_type=dev_type
        )

    def get_available_binaries(self) -> Dict[str, Any]:
        """
        Pywebview bridge endpoint returning all generic binaries in bin_root.
        """
        try:
            bins = binaries.scan_generic_binaries(self.bin_root)
            serializable = []
            for b in bins:
                item = dict(b)
                item["dir_path"] = str(item["dir_path"])
                item["exe_path"] = str(item["exe_path"])
                serializable.append(item)
            return {"success": True, "binaries": serializable}
        except Exception as e:
            return {"success": False, "binaries": [], "error": str(e)}

    def get_model_batch_details(self, model_id: str) -> Dict[str, Any]:
        """
        Gets the model configuration for a selected model (Combobox handler).
        Prioritizes structured .json configuration files, auto-converting from .bat if needed.
        Also resolves the active binary (dedicated priority + generic fallback).
        """
        try:
            scan_res = self.scan_models_and_batches()
            target_model = None
            for m in scan_res.get("models", []):
                if m.get("id") == model_id:
                    target_model = m
                    break

            if not target_model:
                return {"success": False, "error": f"Model '{model_id}' not found."}

            folder = Path(target_model["folder_path"])
            is_newly_generated = False
            json_path = None
            bat_path = None

            # 1. Prioritize existing .json configuration files
            if target_model.get("config_files"):
                json_path = Path(target_model["config_files"][0]["path"])
                if not json_path.exists():
                    json_path = None

            # 2. Check existing batch scripts and convert to .json if needed
            if not json_path and target_model.get("batch_scripts"):
                bat_path = Path(target_model["batch_scripts"][0]["path"])
                conv = batch_manager.convert_bat_to_json(bat_path, overwrite=False)
                if conv.get("success"):
                    json_path = Path(conv["json_path"])

            # 3. If neither exists, auto-generate calibrated .bat and .json templates
            if not json_path:
                weights = target_model.get("weights", [])
                if not weights:
                    return {"success": False, "error": "No model weights found to generate batch script."}
                
                model_file = weights[0]["filename"]
                mmproj_file = target_model["mmproj"][0]["filename"] if target_model.get("mmproj") else None
                family = target_model.get("family", "")
                variant = target_model.get("variant", "")

                slug = target_model["id"].replace("_", "-")
                bat_path = folder / f"run-{slug}.bat"
                
                content = batch_manager.generate_batch_template(
                    model_folder=folder,
                    model_filename=model_file,
                    mmproj_filename=mmproj_file,
                    family_name=family,
                    variant_name=variant
                )
                save_res = batch_manager.save_batch_script(bat_path, content, create_backup=False)
                if not save_res.get("success"):
                    return save_res

                conv = batch_manager.convert_bat_to_json(bat_path, overwrite=True)
                if conv.get("success"):
                    json_path = Path(conv["json_path"])
                is_newly_generated = True

            # 4. Parse JSON configuration
            if json_path and json_path.exists():
                parsed = batch_manager.parse_json_config(json_path)
            elif bat_path and bat_path.exists():
                parsed = batch_manager.parse_batch_script(bat_path)
            else:
                return {"success": False, "error": "Could not resolve configuration file for model."}
            
            # 5. Binary resolution based on configured engine
            configured_engine = parsed.get("engine", "CUDA")
            dev_type = "CPU" if configured_engine == "CPU" else ("VULKAN" if configured_engine == "VULKAN" else "CUDA")

            bin_res = binaries.resolve_model_binary(
                model_folder=folder,
                bin_root=self.bin_root,
                dev_type=dev_type
            )

            parsed["is_newly_generated"] = is_newly_generated
            parsed["binary_info"] = bin_res
            parsed["model_info"] = target_model
            return parsed
        except Exception as e:
            return {"success": False, "error": f"Error loading model batch: {str(e)}"}

    def save_batch_script(self, config_path: str, raw_content: str, create_backup: bool = True) -> Dict[str, Any]:
        """
        Saves updated content to a .json or .bat configuration with automatic backup.
        Automatically keeps both .json and .bat synchronized.
        """
        try:
            p = Path(config_path)
            if p.suffix.lower() == ".json":
                res = batch_manager.save_json_config(p, raw_content, create_backup=create_backup, sync_bat=True)
                return res
            elif p.suffix.lower() == ".bat":
                res = batch_manager.save_batch_script(p, raw_content, create_backup=create_backup)
                if res.get("success"):
                    # Also update/sync .json
                    batch_manager.convert_bat_to_json(p, overwrite=True)
                    res["parsed_config"] = batch_manager.parse_batch_script(p)
                return res
            else:
                return {"success": False, "error": f"Unsupported configuration format: {p.suffix}"}
        except Exception as e:
            return {"success": False, "error": f"Error saving configuration: {str(e)}"}

    def save_model_config(self, config_path: str, raw_content: str, create_backup: bool = True) -> Dict[str, Any]:
        """Alias for save_batch_script with generic configuration semantics."""
        return self.save_batch_script(config_path, raw_content, create_backup=create_backup)

    def launch_batch_script(self, bat_path: str, port: int = 8080) -> Dict[str, Any]:
        """
        Launches a model's .bat script directly as a supervised subprocess group.
        Accepts either a .bat path or a .json configuration path.
        """
        try:
            p = Path(bat_path)
            if p.suffix.lower() == ".json":
                bat_candidate = p.with_suffix(".bat")
                if bat_candidate.exists():
                    p = bat_candidate
                else:
                    return {"success": False, "message": f"Associated batch script not found for {bat_path}"}
            res = self.manager.start_batch_server(p, port=port, logs_dir=self.logs_dir)
            if res.get("success"):
                self._record_model_usage(p.name)
            return res
        except Exception as e:
            return {"success": False, "message": f"Error launching batch script: {str(e)}"}

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

            # 1. Resolve Engine Binary Path (Dedicated priority + Generic fallback)
            bin_info = binaries.resolve_model_binary(
                model_folder=model_path.parent,
                bin_root=self.bin_root,
                dev_type=engine
            )
            if not bin_info.get("success") or not bin_info.get("binary_dir"):
                return {
                    "success": False,
                    "message": f"Could not resolve engine binary for {engine}: {bin_info.get('error', 'Unknown error')}"
                }

            bin_dir = Path(bin_info["binary_dir"])

            # 2. Resolve PolarQuant Flags
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
        info["logs"] = self.manager.get_recent_logs(120)
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

    def check_llama_updates(self, engine: str = "CUDA") -> Dict[str, Any]:
        """
        Queries GitHub API for the latest pre-release/release of llama.cpp,
        extracts the latest build number, compares it against the local build,
        and locates the corresponding Windows x64 binary asset.
        """
        import requests
        try:
            # Detect currently active/installed build for the selected engine
            resolved = binaries.resolve_model_binary(bin_root=self.bin_root, dev_type=engine)
            current_build_num = resolved.get("build_num", 0)
            current_build = resolved.get("build", "unknown")
            if current_build == "unknown" and current_build_num:
                current_build = f"b{current_build_num}"

            # Query GitHub Releases (per_page=10 to include latest pre-releases like b11368)
            headers = {"User-Agent": "LlamaLaunch-Desktop/2.1"}
            resp = requests.get(
                "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10",
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            releases_data = resp.json()

            target_release = None
            latest_build_num = 0
            latest_tag = ""
            for rel in releases_data:
                tag = rel.get("tag_name", "")
                m = re.match(r"^b(\d+)$", tag, re.IGNORECASE)
                if m:
                    b_num = int(m.group(1))
                    if b_num > latest_build_num:
                        latest_build_num = b_num
                        latest_tag = tag
                        target_release = rel

            if not target_release:
                return {
                    "success": False,
                    "message": "No se encontraron releases con formato de compilación bXXXX en GitHub."
                }

            engine_upper = (engine or "CUDA").upper()
            assets = target_release.get("assets", [])
            chosen_asset = None

            if engine_upper == "CUDA":
                cuda13_assets = [
                    a for a in assets 
                    if a.get("name", "").lower().startswith("llama-") 
                    and "cudart" not in a.get("name", "").lower() 
                    and "bin-win-cuda-13" in a.get("name", "").lower() 
                    and "x64.zip" in a.get("name", "").lower() 
                    and "arm64" not in a.get("name", "").lower()
                ]
                cuda_assets = [
                    a for a in assets 
                    if a.get("name", "").lower().startswith("llama-") 
                    and "cudart" not in a.get("name", "").lower() 
                    and "bin-win-cuda" in a.get("name", "").lower() 
                    and "x64.zip" in a.get("name", "").lower() 
                    and "arm64" not in a.get("name", "").lower()
                ]
                if cuda13_assets:
                    chosen_asset = cuda13_assets[0]
                elif cuda_assets:
                    chosen_asset = cuda_assets[0]
            elif engine_upper == "VULKAN":
                vulkan_assets = [
                    a for a in assets 
                    if a.get("name", "").lower().startswith("llama-") 
                    and "cudart" not in a.get("name", "").lower() 
                    and "bin-win-vulkan" in a.get("name", "").lower() 
                    and "x64.zip" in a.get("name", "").lower() 
                    and "arm64" not in a.get("name", "").lower()
                ]
                if vulkan_assets:
                    chosen_asset = vulkan_assets[0]
            else:
                cpu_assets = [
                    a for a in assets 
                    if a.get("name", "").lower().startswith("llama-") 
                    and "cudart" not in a.get("name", "").lower() 
                    and "bin-win-cpu" in a.get("name", "").lower() 
                    and "x64.zip" in a.get("name", "").lower() 
                    and "arm64" not in a.get("name", "").lower()
                ]
                if cpu_assets:
                    chosen_asset = cpu_assets[0]

            has_update = latest_build_num > current_build_num

            body = target_release.get("body", "").strip()
            if len(body) > 600:
                body = body[:600] + "..."

            return {
                "success": True,
                "has_update": has_update,
                "current_version": current_build,
                "current_build_num": current_build_num,
                "latest_version": latest_tag,
                "latest_build_num": latest_build_num,
                "release_name": target_release.get("name") or latest_tag,
                "release_notes": body,
                "html_url": target_release.get("html_url", "https://github.com/ggml-org/llama.cpp/releases"),
                "published_at": target_release.get("published_at", ""),
                "asset_name": chosen_asset.get("name") if chosen_asset else None,
                "download_url": chosen_asset.get("browser_download_url") if chosen_asset else None,
                "size_mb": round(chosen_asset.get("size", 0) / (1024 * 1024), 1) if chosen_asset else 0,
                "engine": engine_upper
            }
        except Exception as e:
            return {"success": False, "message": f"Error al verificar actualizaciones en GitHub: {str(e)}"}

    def download_and_install_llama_update(self, download_url: str, asset_name: str, engine: str) -> Dict[str, Any]:
        """
        Streams download of the llama.cpp release zip in a background thread,
        extracts it into the bin directory, copies CUDA runtime DLLs if needed,
        and notifies the frontend via evaluate_js.
        """
        if not download_url:
            return {"success": False, "message": "URL de descarga inválida."}

        thread = threading.Thread(
            target=self._worker_install_llama_update,
            args=(download_url, asset_name, engine),
            daemon=True
        )
        thread.start()
        return {"success": True, "message": "Iniciando descarga e instalación en segundo plano."}

    def _worker_install_llama_update(self, download_url: str, asset_name: str, engine: str):
        import requests
        import zipfile
        import time

        temp_dir = self.logs_dir / "temp_updates"
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / (asset_name or "llama_update.zip")

        start_time = time.time()
        last_update_time = 0

        def emit_js(percent, speed, downloaded_mb, total_mb, status, message=""):
            if self._window:
                msg_escaped = message.replace("'", "\\'").replace('"', '\\"')
                js_call = f"window.updateLlamaUpdateProgress({percent:.1f}, {speed:.2f}, {downloaded_mb:.1f}, {total_mb:.1f}, '{status}', '{msg_escaped}')"
                try:
                    self._window.evaluate_js(js_call)
                except Exception:
                    pass

        try:
            emit_js(0.0, 0.0, 0.0, 0.0, 'downloading', 'Iniciando conexión con GitHub...')
            headers = {'User-Agent': 'LlamaLaunch-Desktop/2.1'}
            response = requests.get(download_url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 1024 * 512

            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        curr_time = time.time()
                        if curr_time - last_update_time >= 0.2:
                            last_update_time = curr_time
                            duration = curr_time - start_time
                            speed = (downloaded / (1024 * 1024 * duration)) if duration > 0 else 0
                            percent = (downloaded / total_size * 100) if total_size > 0 else 0
                            d_mb = downloaded / (1024 * 1024)
                            t_mb = total_size / (1024 * 1024)
                            emit_js(percent, speed, d_mb, t_mb, 'downloading')

            total_mb = total_size / (1024 * 1024)
            emit_js(100.0, 0.0, total_mb, total_mb, 'extracting', 'Extrayendo binarios y configurando DLLs...')

            m_tag = re.search(r"b(\d+)", asset_name, re.IGNORECASE)
            build_tag = f"b{m_tag.group(1)}" if m_tag else "latest"
            engine_str = (engine or "cuda").lower()
            target_folder_name = f"llama-{build_tag}-bin-win-{engine_str}-x64"

            dest_dirs = [self.bin_root / target_folder_name]
            local_bin_root = self.project_root / "llamaLauncher" / "bin" / "llama.cpp"
            if local_bin_root.resolve() != self.bin_root.resolve():
                dest_dirs.append(local_bin_root / target_folder_name)

            for dest_dir in dest_dirs:
                dest_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(dest_dir)

                if engine_str == "cuda":
                    hardware.check_and_copy_cuda_dlls(dest_dir, self.bin_root)
                    if local_bin_root.exists() and local_bin_root != self.bin_root:
                        hardware.check_and_copy_cuda_dlls(dest_dir, local_bin_root)

            try:
                zip_path.unlink()
            except Exception:
                pass

            emit_js(100.0, 0.0, total_mb, total_mb, 'completed', f'¡Actualización {build_tag} instalada exitosamente!')

        except Exception as e:
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            emit_js(0.0, 0.0, 0.0, 0.0, 'error', f'Fallo en la instalación: {str(e)}')
