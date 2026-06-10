import os
import sys
from pathlib import Path
import webview

def resolve_project_root() -> Path:
    """
    Resolves the project root directory.
    - Compiled .exe: the directory containing the .exe
    - Python script: llamaLauncher/../ (parent of the llamaLauncher package)
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller compiled .exe — user places .exe in project root
        return Path(sys.executable).resolve().parent
    else:
        # Running as Python script — app.py is inside llamaLauncher/
        return Path(__file__).resolve().parent.parent

def get_resource_path(relative_path: str) -> Path:
    """
    Resolves resource paths dynamically.
    Supports standard execution in development, and handles PyInstaller self-unpacking
    temporary directory ('sys._MEIPASS') for production compiled executables.
    """
    try:
        # PyInstaller temp folder
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = resolve_project_root()
        
    return base_path / relative_path

# Resolve project root early
PROJECT_ROOT = resolve_project_root()

# Add project root to sys.path for package imports
sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.api import ApiBridge

def main():
    """
    Main application entry point for llamaLauncher.
    Initializes pywebview and handles self-unpacking assets safely.
    """
    # Resolve index.html path dynamically matching new llamaLauncher/app/frontend structure
    html_path = get_resource_path("llamaLauncher/app/frontend/index.html")
    
    if not html_path.exists():
        # Fallback: try relative to script directory
        html_path = Path(__file__).resolve().parent / "app" / "frontend" / "index.html"
    
    if not html_path.exists():
        print(f"[FATAL] Could not find index.html at: {html_path}")
        sys.exit(1)
    
    # 1. Instantiate the API Facade Bridge with explicit project root
    bridge = ApiBridge(project_root=str(PROJECT_ROOT))
    
    # 2. Configure and create native OS desktop window
    window = webview.create_window(
        title="AI Local — Desktop Inference Suite",
        url=str(html_path),
        js_api=bridge,
        width=1150,
        height=780,
        resizable=True,
        min_size=(950, 650)
    )
    
    # Set the window reference in the API bridge for evaluate_js calls
    bridge.set_window(window)
    
    # 3. Graceful termination handler
    def on_closed():
        bridge.stop_server()
        
    window.events.closed += on_closed
    
    # 4. Start the pywebview graphical loop
    #    http_server=True: serves files via built-in HTTP server,
    #    avoiding direct WebView2 file:// COM issues that cause
    #    recursion overflow (Font.Style.Bold...) and E_NOINTERFACE crashes.
    #    debug=True: enables DevTools (right-click -> Inspect Element)
    webview.start(
        debug=True,
        http_server=True,
        private_mode=False
    )

if __name__ == "__main__":
    main()
