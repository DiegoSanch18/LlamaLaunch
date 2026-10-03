try:
    from app.backend.config import patch_pywebview_bottle
except ImportError:
    from llamaLauncher.app.backend.config import patch_pywebview_bottle
