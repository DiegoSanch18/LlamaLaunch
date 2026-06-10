import subprocess
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional

class ProcessManager:
    """
    Singleton class managing the lifecycle of the llama-server subprocess.
    Ensures only a single instance of the server runs, handles OS detection,
    and supports non-blocking operations with log monitoring and health-checks.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProcessManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.process: Optional[subprocess.Popen] = None
        self.status = "STOPPED"  # "STOPPED", "LOADING", "RUNNING"
        self.active_port = 8080
        self.active_model = ""
        self.active_log_path: Optional[Path] = None
        self.history_log_path: Optional[Path] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitor_event = threading.Event()

    def kill_all_zombies(self):
        """
        Force-kills any residual llama-server processes in the OS to release VRAM/RAM.
        """
        self.status = "STOPPED"
        try:
            if sys.platform == "win32":
                subprocess.run(
                    "taskkill /f /im llama-server.exe", 
                    shell=True, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.run(
                    "killall -9 llama-server", 
                    shell=True, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            pass

    def start_server(
        self, 
        bin_dir: Path, 
        model_path: Path, 
        port: int, 
        threads: int, 
        context: int, 
        ngl: int, 
        polar_flags: str, 
        logs_dir: Path,
        context_shift: bool = True
    ) -> Dict[str, Any]:
        """
        Launches the llama-server in a background thread.
        Uses process polling and endpoint health-checking to update state smoothly.
        """
        with self._lock:
            if self.status in ("LOADING", "RUNNING"):
                return {"success": False, "message": "The server is already active or loading."}

            self.status = "LOADING"
            self.active_port = port
            self.active_model = model_path.name
            
            # Setup logs
            logs_dir.mkdir(parents=True, exist_ok=True)
            self.active_log_path = logs_dir / "active_server.log"
            self.history_log_path = logs_dir / "server_history.log"

            # Clean active log
            if self.active_log_path.exists():
                try:
                    self.active_log_path.unlink()
                except Exception:
                    pass

            # Log history
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(self.history_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] Started: {model_path.name} | Port: {port} | NGL: {ngl} | PQ: {polar_flags} | Shift: {context_shift}\n")
            except Exception:
                pass

            # Make sure no zombie exists
            self.kill_all_zombies()
            self.status = "LOADING" # Reset since kill_all_zombies sets to STOPPED

            # Build execution command
            exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
            exe_path = bin_dir / exe_name

            if not exe_path.exists():
                self.status = "STOPPED"
                return {
                    "success": False, 
                    "message": f"Executable not found at: {exe_path}. Please download the correct binary."
                }

            cmd = [
                str(exe_path),
                "-m", str(model_path),
                "--host", "0.0.0.0",
                "--port", str(port),
                "-t", str(threads),
                "-c", str(context),
                "-ngl", str(ngl)
            ]

            if polar_flags:
                for flag in polar_flags.split():
                    cmd.append(flag)
            
            if context_shift:
                cmd.append("--context-shift")

            # Launch in background
            try:
                # Redirect outputs to active_server.log
                log_file = open(self.active_log_path, "w", encoding="utf-8")
                
                # Platform-specific subprocess flags
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
                
                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(bin_dir),
                    stdout=log_file,
                    stderr=log_file,
                    creationflags=creation_flags
                )
                
                # Start non-blocking monitor thread
                self.stop_monitor_event.clear()
                self.monitor_thread = threading.Thread(
                    target=self._monitor_server_lifecycle, 
                    args=(port, log_file), 
                    daemon=True
                )
                self.monitor_thread.start()

                return {
                    "success": True, 
                    "message": "Server subprocess started in background. Loading model weights..."
                }

            except Exception as e:
                self.status = "STOPPED"
                return {"success": False, "message": f"Failed to launch subprocess: {str(e)}"}

    def stop_server(self) -> Dict[str, Any]:
        """
        Safely stops the active server.
        """
        with self._lock:
            self.status = "STOPPED"
            self.stop_monitor_event.set()
            
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None

            # Extra cleanup
            self.kill_all_zombies()
            return {"success": True, "message": "Server stopped and memory instances released."}

    def get_status_info(self) -> Dict[str, Any]:
        """
        Returns status dictionary for frontend.
        Thread-safe: captures process reference locally to prevent
        race condition with stop_server() modifying self.process.
        """
        proc = self.process  # Local ref — avoids TOCTOU race
        pid = None
        try:
            if proc:
                pid = proc.pid
        except Exception:
            pass
        return {
            "status": self.status,
            "port": self.active_port,
            "model": self.active_model,
            "pid": pid
        }

    def get_recent_logs(self, max_lines: int = 30) -> List[str]:
        """
        Reads and returns the last N lines of active_server.log.
        """
        if not self.active_log_path or not self.active_log_path.exists():
            return ["[SYSTEM] Waiting for log file to initialize..."]

        try:
            with open(self.active_log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return [line.rstrip() for line in lines[-max_lines:]]
        except Exception as e:
            return [f"[SYSTEM ERROR] Could not read log file: {e}"]

    def _monitor_server_lifecycle(self, port: int, log_file_handle):
        """
        Runs in a background thread to check:
        1. If process dies early.
        2. When the server is fully ready to accept HTTP connections (polling /health).
        """
        check_url = f"http://127.0.0.1:{port}/health"
        retries = 90  # up to 90 seconds wait for heavy models
        
        while not self.stop_monitor_event.is_set():
            # 1. Check if process has terminated
            if self.process:
                ret_code = self.process.poll()
                if ret_code is not None:
                    # Process died!
                    self.status = "STOPPED"
                    try:
                        log_file_handle.close()
                    except Exception:
                        pass
                    break
            
            # 2. Check HTTP health endpoint if still "LOADING"
            if self.status == "LOADING":
                try:
                    req = urllib.request.Request(check_url, method="GET")
                    with urllib.request.urlopen(req, timeout=1.0) as response:
                        if response.status == 200:
                            self.status = "RUNNING"
                except Exception:
                    # Connection refused or server still initializing
                    pass
            
            time.sleep(1.0)
            retries -= 1
            if retries <= 0 and self.status == "LOADING":
                # Timeout
                self.status = "STOPPED"
                if self.process:
                    try:
                        self.process.terminate()
                    except Exception:
                        pass
                break
                
        try:
            log_file_handle.close()
        except Exception:
            pass

class DownloadManager:
    """
    Singleton manager for asynchronous, non-blocking model downloads.
    Uses requests stream=True to download GGUF models from Hugging Face or direct URLs.
    Reports progress in real-time to the pywebview frontend using window.evaluate_js().
    Supports cancellation and handles cleanup of temporary .part files on failure or cancellation.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DownloadManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.active_downloads = {}  # target_path_str -> thread
        self.cancel_flags = {}      # target_path_str -> threading.Event

    def start_download(self, url: str, target_path: Path, category: str, window) -> Dict[str, Any]:
        """
        Starts a background thread to download a model.
        Returns a dict indicating if the thread was launched successfully.
        """
        if target_path.exists():
            return {"success": False, "message": "Model file already exists locally."}

        target_str = str(target_path)
        if target_str in self.active_downloads:
            return {"success": False, "message": "A download for this model is already in progress."}

        # Setup cancel flag
        cancel_event = threading.Event()
        self.cancel_flags[target_str] = cancel_event

        # Spawn download thread
        thread = threading.Thread(
            target=self._download_worker,
            args=(url, target_path, category, cancel_event, window),
            daemon=True
        )
        self.active_downloads[target_str] = thread
        thread.start()

        return {"success": True, "message": "Download started successfully."}

    def cancel_download(self, target_path_str: str) -> bool:
        """
        Signals the download thread to stop and clean up.
        """
        if target_path_str in self.cancel_flags:
            self.cancel_flags[target_path_str].set()
            return True
        return False

    def _download_worker(self, url: str, target_path: Path, category: str, cancel_event: threading.Event, window):
        import requests
        target_str = str(target_path)
        part_path = target_path.with_suffix(".part")

        if part_path.exists():
            try:
                part_path.unlink()
            except Exception:
                pass

        start_time = time.time()
        last_update_time = 0

        try:
            # 1. Start streaming download
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
            }
            response = requests.get(url, stream=True, headers=headers, timeout=20)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 1024 * 512  # 512 KB chunks for smooth downloads

            with open(part_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    # Check for cancellation
                    if cancel_event.is_set():
                        raise InterruptedError("Download cancelled by user.")

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Throttle JS updates to prevent interface lagging (every 0.2s)
                        current_time = time.time()
                        if current_time - last_update_time >= 0.25:
                            last_update_time = current_time
                            duration = current_time - start_time
                            speed = downloaded / (1024 * 1024 * duration) if duration > 0 else 0
                            percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                            
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)

                            # Stream progress directly to JS via evaluate_js
                            if window:
                                js_call = f"window.updateDownloadProgress({percent:.1f}, {speed:.2f}, {downloaded_mb:.1f}, {total_mb:.1f}, 'downloading', '', '{category}', '{target_path.name}')"
                                window.evaluate_js(js_call)

            # 2. Check cancellation one last time
            if cancel_event.is_set():
                raise InterruptedError("Download cancelled by user.")

            # Rename .part file to final GGUF filename
            if target_path.exists():
                target_path.unlink()
            part_path.rename(target_path)

            # Report success
            if window:
                total_mb = total_size / (1024 * 1024)
                js_call = f"window.updateDownloadProgress(100.0, 0.0, {total_mb:.1f}, {total_mb:.1f}, 'completed', '', '{category}', '{target_path.name}')"
                window.evaluate_js(js_call)

        except InterruptedError:
            # User cancellation cleanup
            if part_path.exists():
                try:
                    part_path.unlink()
                except Exception:
                    pass
            if window:
                js_call = f"window.updateDownloadProgress(0.0, 0.0, 0.0, 0.0, 'cancelled', '', '{category}', '{target_path.name}')"
                window.evaluate_js(js_call)

        except Exception as e:
            # Network cut or file error cleanup
            if part_path.exists():
                try:
                    part_path.unlink()
                except Exception:
                    pass
            error_msg = str(e).replace("'", "\\'")
            if window:
                js_call = f"window.updateDownloadProgress(0.0, 0.0, 0.0, 0.0, 'error', '{error_msg}', '{category}', '{target_path.name}')"
                window.evaluate_js(js_call)

        finally:
            # Cleanup registry
            self.active_downloads.pop(target_str, None)
            self.cancel_flags.pop(target_str, None)
