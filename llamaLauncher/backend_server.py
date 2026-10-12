"""
LlamaLaunch Backend API Server (Decoupled Microservice Mode :5000)
==================================================================
Exposes the full ApiBridge JSON-RPC interface and system integration endpoints
over HTTP on port 5000, fully decoupled from the Nginx frontend (:3000).

Provides:
- POST /api/call               : JSON-RPC dispatcher for ApiBridge methods
- GET  /api/health             : Backend health check and models summary
- GET  /api/gateway/status     : Health status probe for LlamaLaunch Gateway (:8081 / :8082)
- GET  /api/atomic/status      : Health status probe for Atomic AI Cognitive Proxy (:8000)
- POST /api/atomic/test        : End-to-end verification through Atomic AI & Gateway pipeline
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any
from bottle import Bottle, request, response
import requests

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llamaLauncher.app.backend.api import ApiBridge
from llamaLauncher.app.backend.gateway import get_gateway

logger = logging.getLogger("LlamaLaunch.Backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Bottle()
bridge = ApiBridge(project_root=str(PROJECT_ROOT))


class WebWindowShim:
    """Shim for pywebview window so evaluate_js does not crash when called from background threads."""
    def evaluate_js(self, script: str):
        pass


bridge.set_window(WebWindowShim())

# Configuration from environment
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5000"))
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8082").rstrip("/")
ATOMIC_PROXY_URL = os.getenv("ATOMIC_PROXY_URL", "http://host.docker.internal:8000").rstrip("/")
DEFAULT_LOCAL_BACKEND = os.getenv("DEFAULT_LOCAL_BACKEND", "http://host.docker.internal:8080").rstrip("/")


def _set_cors_headers():
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-target-backend")


# ------------------------------------------------------------------------------
# 1. CORS Preflight
# ------------------------------------------------------------------------------
@app.route("/api/<path:path>", method=["OPTIONS"])
def api_options(path=""):
    _set_cors_headers()
    return {}


# ------------------------------------------------------------------------------
# 2. PyWebView Bridge Emulation via HTTP POST /api/call
# ------------------------------------------------------------------------------
@app.route("/api/call", method=["POST"])
def api_call():
    _set_cors_headers()

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


# ------------------------------------------------------------------------------
# 3. Health & Environment Status
# ------------------------------------------------------------------------------
@app.route("/api/health")
def health():
    _set_cors_headers()
    models_dir = getattr(bridge, "models_dir", None)
    return {
        "status": "ok",
        "service": "LlamaLaunch Decoupled Backend",
        "port": BACKEND_PORT,
        "models_dir": str(models_dir) if models_dir else "unknown",
        "active_model": getattr(bridge.manager, "active_model", "") or "None",
        "server_status": getattr(bridge.manager, "status", "STOPPED")
    }


# ------------------------------------------------------------------------------
# 4. Gateway Integration Status (:8081 / :8082)
# ------------------------------------------------------------------------------
@app.route("/api/gateway/status")
def gateway_status():
    _set_cors_headers()
    explicit_url = request.query.get("url")
    if explicit_url:
        candidates = [explicit_url.strip()]
    else:
        candidates = [GATEWAY_URL]
        if "host.docker.internal" not in GATEWAY_URL:
            candidates.append("http://host.docker.internal:8081")
            candidates.append("http://host.docker.internal:8082")

    for url in candidates:
        try:
            resp = requests.get(f"{url}/health", timeout=0.3)
            if resp.status_code in (200, 503):
                data = resp.json()
                data["reachable"] = True
                data["gateway_url"] = url
                return data
        except Exception:
            continue

    return {
        "status": "offline",
        "reachable": False,
        "gateway_url": explicit_url or GATEWAY_URL,
        "message": f"Gateway not reachable at {explicit_url or GATEWAY_URL}"
    }


# ------------------------------------------------------------------------------
# 5. Atomic AI Proxy Integration Status (:8000)
# ------------------------------------------------------------------------------
@app.route("/api/atomic/status")
def atomic_status():
    _set_cors_headers()
    explicit_url = request.query.get("url")
    if explicit_url:
        candidates = [explicit_url.strip()]
    else:
        candidates = [ATOMIC_PROXY_URL]
        if "host.docker.internal" not in ATOMIC_PROXY_URL:
            candidates.append("http://atomic-proxy:8000")
            candidates.append("http://host.docker.internal:8000")

    for url in candidates:
        try:
            # Check OpenAPI / models / health endpoint of Atomic AI
            resp = requests.get(f"{url}/health", timeout=0.3)
            if resp.status_code == 200:
                data = resp.json()
                data["reachable"] = True
                data["atomic_url"] = url
                return data
        except Exception:
            try:
                resp = requests.get(f"{url}/v1/models", timeout=0.3)
                if resp.status_code == 200:
                    return {
                        "status": "online",
                        "reachable": True,
                        "atomic_url": url,
                        "models": resp.json()
                    }
            except Exception:
                continue

    return {
        "status": "offline",
        "reachable": False,
        "atomic_url": explicit_url or ATOMIC_PROXY_URL,
        "message": f"Atomic AI Proxy not reachable at {explicit_url or ATOMIC_PROXY_URL}"
    }


# ------------------------------------------------------------------------------
# 6. Test Inference through Pipeline
# ------------------------------------------------------------------------------
@app.route("/api/atomic/test", method=["POST"])
def atomic_test():
    _set_cors_headers()
    try:
        raw = request.body.read()
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        body = {}

    prompt = body.get("prompt", "¿Qué es un modelo de lenguaje SLM?")
    target_proxy = body.get("proxy_url") or ATOMIC_PROXY_URL
    model = body.get("model", "gemma-4-e2b")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 150
    }

    try:
        resp = requests.post(f"{target_proxy}/v1/chat/completions", json=payload, timeout=60.0)
        return {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "response": resp.json() if resp.status_code == 200 else resp.text
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "5000"))

    logger.info(f"LlamaLaunch Decoupled Backend starting on http://{host}:{port}")
    logger.info(f"Models directory: {bridge.models_dir}")
    logger.info(f"Target Gateway URL: {GATEWAY_URL}")
    logger.info(f"Target Atomic AI Proxy URL: {ATOMIC_PROXY_URL}")

    app.run(host=host, port=port, server="wsgiref", quiet=False)


if __name__ == "__main__":
    main()
