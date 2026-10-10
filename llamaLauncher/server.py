"""
LlamaLaunch Web Server (Headless / Containerized Mode)
======================================================
Serves the LlamaLaunch HTML5/CSS/JS frontend directly over standard HTTP (:3000),
exposing all ApiBridge methods via JSON RPC / REST so that any web browser
can interact directly with the suite without requiring a virtual Linux desktop (XFCE/Webtop).
"""

import sys
import os
import json
import logging
from pathlib import Path
from bottle import Bottle, request, response, static_file

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llamaLauncher.app.backend.api import ApiBridge
from llamaLauncher.app.backend.gateway import get_gateway

logger = logging.getLogger("LlamaLaunch.WebServer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Bottle()
FRONTEND_DIR = Path(__file__).resolve().parent / "app" / "frontend"
bridge = ApiBridge(project_root=str(PROJECT_ROOT))


class WebWindowShim:
    """Shim for pywebview window so evaluate_js does not crash when called from background threads."""
    def evaluate_js(self, script: str):
        pass


bridge.set_window(WebWindowShim())


# ------------------------------------------------------------------------------
# 1. Static Frontend Assets
# ------------------------------------------------------------------------------
@app.route("/")
@app.route("/index.html")
def index():
    return static_file("index.html", root=str(FRONTEND_DIR))


@app.route("/<filename:path>")
def static_assets(filename):
    return static_file(filename, root=str(FRONTEND_DIR))


# ------------------------------------------------------------------------------
# 2. PyWebView Bridge Emulation via HTTP POST /api/call
# ------------------------------------------------------------------------------
@app.route("/api/call", method=["POST", "OPTIONS"])
def api_call():
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    response.set_header("Access-Control-Allow-Headers", "Content-Type")

    if request.method == "OPTIONS":
        return {}

    try:
        raw_body = request.body.read()
        if raw_body:
            data = json.loads(raw_body.decode("utf-8"))
        else:
            data = request.json or {}

        method_name = data.get("method")
        args = data.get("params", [])

        if not method_name:
            response.status = 400
            return {"success": False, "error": "Missing 'method' parameter"}

        target_method = getattr(bridge, method_name, None)
        if not target_method or not callable(target_method):
            response.status = 404
            return {"success": False, "error": f"Method '{method_name}' not found on ApiBridge"}

        if isinstance(args, list):
            result = target_method(*args)
        elif isinstance(args, dict):
            result = target_method(**args)
        else:
            result = target_method()

        response.content_type = "application/json; charset=utf-8"
        return json.dumps(result, default=str)
    except Exception as e:
        logger.exception(f"Error executing API method: {e}")
        response.status = 500
        return {"success": False, "error": str(e)}


@app.route("/api/health")
def health():
    return {"status": "ok", "service": "LlamaLaunch Web Suite"}


def main():
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "3000"))

    # Also start background inference gateway if requested
    try:
        gw = get_gateway()
        gw.start()
        logger.info(f"Background Inference Gateway running on port {gw.port}")
    except Exception as e:
        logger.warning(f"Could not start Inference Gateway: {e}")

    logger.info(f"LlamaLaunch Web Suite starting on http://{host}:{port}")
    app.run(host=host, port=port, server="wsgiref", quiet=False)


if __name__ == "__main__":
    main()
