import os
import sys
import inspect
from pathlib import Path
import webview

def patch_pywebview_bottle():
    """
    Hotfix for pywebview 5.x / Bottle routing on Python 3.13+:
    When http_server=True, pywebview registers static assets using:
        @app.route('/')
        @app.route('/<file:path>')
        def asset(file):
    When requesting the root URL '/', Bottle calls asset() without arguments,
    causing 'TypeError: asset() missing 1 required positional argument: file' (HTTP 500).
    This patch ensures that if 'file' has no default, it defaults to 'index.html'.
    """
    try:
        import bottle
        if getattr(bottle.Bottle, '_llamalaunch_patched', False):
            return
        _orig_route = bottle.Bottle.route
        def _safe_route(self, path=None, method='GET', callback=None, **options):
            decorator = _orig_route(self, path, method, callback, **options)
            def wrapper(func):
                try:
                    sig = inspect.signature(func)
                    if 'file' in sig.parameters and sig.parameters['file'].default is inspect.Parameter.empty:
                        def fixed_asset(file='index.html', *args, **kwargs):
                            return func(file, *args, **kwargs)
                        return decorator(fixed_asset)
                except Exception:
                    pass
                return decorator(func)
            return wrapper if callback is None else wrapper(callback)
        bottle.Bottle.route = _safe_route
        bottle.Bottle._llamalaunch_patched = True
    except Exception as e:
        print(f"[WARN] Could not patch Bottle routing: {e}")

# Apply patch early before webview.start is invoked
patch_pywebview_bottle()

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

# Add project root and script directory to sys.path for package imports
launcher_dir = Path(__file__).resolve().parent
if str(launcher_dir) not in sys.path:
    sys.path.insert(0, str(launcher_dir))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from llamaLauncher.app.backend.api import ApiBridge
except ImportError:
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
