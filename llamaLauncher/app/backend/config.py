from typing import Dict, Any, Tuple

# Default configuration profiles
DEFAULT_GPU_OFFLOAD = 99
DEFAULT_CPU_OFFLOAD = 0

def optimize_params(dev_type: str, physical_cores: int, pq_choice: str = "3") -> Dict[str, Any]:
    """
    Optimizes server execution parameters based on hardware and engine.
    Adapts context size dynamically if PolarQuant cache compression is enabled.
    """
    config = {}
    
    # 1. Threads optimization
    config["threads"] = max(1, physical_cores)
    
    # 2. Base Port
    config["port"] = 8080
    
    # 3. NGL (Offloading) based on device type
    if dev_type == "CPU":
        config["ngl"] = DEFAULT_CPU_OFFLOAD
    else:
        config["ngl"] = DEFAULT_GPU_OFFLOAD

    # 4. Adjust context size based on PolarQuant choice
    context_multiplier = 1024  # Base multiplier for context size    
    if pq_choice in ("4", "1"):
        base_context = 32 * context_multiplier  # 32K for Ultra Performance / Performance Mode
    elif pq_choice == "5":
        base_context = 24 * context_multiplier  # 24K for Balanced Mode
    elif pq_choice in ("6", "2"):
        base_context = 16 * context_multiplier  # 16K for High / Max Quality Mode
    else:
        base_context = 8 * context_multiplier  # 8K for Standard Mode

    # Cap context for CPU execution to prevent system RAM starvation and compute stalls
    if dev_type == "CPU":
        config["context"] = min(base_context, 16 * context_multiplier)
    else:
        config["context"] = base_context
    return config

def get_polar_quant_flags(pq_choice: str) -> Tuple[str, str]:
    """
    Translates user choice into actual llama-server CLI flags for PolarQuant.
    Returns (flags_string, status_string).
    """
    choice = str(pq_choice).lower().strip()
    if choice in ("iq4_nl", "rendimiento"):
        return "--cache-type-k iq4_nl --cache-type-v iq4_nl -fa on", "Enabled (Rendimiento: iq4_nl + Flash Attention)"
    elif choice in ("q4_0", "ultra_rendimiento", "1", "4"):
        return "--cache-type-k q4_0 --cache-type-v q4_0 -fa on", "Enabled (Ultra Rendimiento: q4_0 + Flash Attention)"
    elif choice in ("q5_0", "equilibrado", "5"):
        return "--cache-type-k q5_0 --cache-type-v q5_0 -fa on", "Enabled (Equilibrado: q5_0 + Flash Attention)"
    elif choice in ("q8_0", "calidad", "2"):
        return "--cache-type-k q8_0 --cache-type-v q8_0 -fa on", "Enabled (Calidad: q8_0 + Flash Attention)"
    else:
        # Standard Mode
        return "", "Disabled (Standard FP16)"

def patch_pywebview_bottle() -> bool:
    """
    Hotfix for pywebview 5.x / Bottle routing on Python 3.13+:
    When http_server=True, pywebview registers static assets using:
        @app.route('/')
        @app.route('/<file:path>')
        def asset(file):
    When requesting the root URL '/', Bottle calls asset() without arguments,
    causing 'TypeError: asset() missing 1 required positional argument: file' (HTTP 500).
    This patch ensures that if 'file' has no default, it defaults to 'index.html'.
    Returns True if patch applied or already active, False if failed.
    """
    try:
        import inspect
        import bottle
        if getattr(bottle.Bottle, '_llamalaunch_patched', False):
            return True
        _orig_route = bottle.Bottle.route
        def _safe_route(self, path=None, method='GET', callback=None, **options):
            decorator = _orig_route(self, path, method, callback, **options)
            def wrapper(func):
                try:
                    sig = inspect.signature(func)
                    if 'file' in sig.parameters and sig.parameters['file'].default is inspect.Parameter.empty:
                        def fixed_asset(file='index.html', *args, **kwargs):
                            try:
                                bottle.response.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                                bottle.response.set_header('Pragma', 'no-cache')
                                bottle.response.set_header('Expires', '0')
                            except Exception:
                                pass
                            return func(file, *args, **kwargs)
                        return decorator(fixed_asset)
                    else:
                        def nocache_asset(*args, **kwargs):
                            try:
                                bottle.response.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                                bottle.response.set_header('Pragma', 'no-cache')
                                bottle.response.set_header('Expires', '0')
                            except Exception:
                                pass
                            return func(*args, **kwargs)
                        return decorator(nocache_asset)
                except Exception:
                    pass
                return decorator(func)
            return wrapper if callback is None else wrapper(callback)
        bottle.Bottle.route = _safe_route
        bottle.Bottle._llamalaunch_patched = True
        return True
    except Exception as e:
        print(f"[WARN] Could not patch Bottle routing: {e}")
        return False

