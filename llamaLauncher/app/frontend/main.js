// main.js - Core JS Controller and Shared State

let api = null;
let currentTab = 'control';
let logPoller = null;
let lastLogText = ""; // To prevent unnecessary console updates
let terminalScrolledToBottom = true;
let scannedModelsMap = {};
let downloadStartTime = null;
let activeDownloadName = "";
let activeDownloadCategory = "";
let isPolling = false; // Guard flag to prevent concurrent poll API calls
let localModelsSort = { key: "name", direction: "asc" };

// 1. Wait for pywebview bridge initialization or initialize HTTP API client
function createHttpApiBridge() {
    const apiBase = window.BACKEND_API_BASE || "";
    return new Proxy({}, {
        get(target, propKey) {
            return async function(...args) {
                try {
                    const response = await fetch(apiBase + "/api/call", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ method: propKey, params: args })
                    });
                    if (!response.ok) {
                        const err = await response.json().catch(() => ({}));
                        throw new Error(err.error || `HTTP ${response.status}`);
                    }
                    return await response.json();
                } catch (err) {
                    console.error(`[API Error] ${propKey}:`, err);
                    return { success: false, message: err.message };
                }
            };
        }
    });
}

window.addEventListener('pywebviewready', () => {
    api = window.pywebview.api;
    initApp();
});

// If running in a regular web browser (Docker / Web mode)
window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (!api && (!window.pywebview || !window.pywebview.api)) {
            console.log("[SYSTEM] Connecting via Web Browser HTTP Bridge (/api/call)...");
            api = createHttpApiBridge();
            initApp();
        }
    }, 150);
});

async function initApp() {
    appendLogLine("[SYSTEM] Initializing communication bridge with Python Backend...");
    
    // Track scroll events on terminal console to maintain smart auto-scroll
    const terminal = document.getElementById("console-terminal");
    if (terminal) {
        terminal.addEventListener("scroll", () => {
            terminalScrolledToBottom = (terminal.scrollHeight - terminal.clientHeight - terminal.scrollTop) < 30;
        });
    }
    
    if (typeof initLocalModelsTableSorting === 'function') {
        initLocalModelsTableSorting();
    }

    // A. Load Hardware Information (each step isolated to prevent cascade failures)
    try {
        const hw = await api.get_hardware_info();
        appendLogLine(`[SYSTEM] CPU Detected: ${hw.physical_cores} physical cores / ${hw.logical_cores} logical threads.`);
        
        // Populate optimal thread default
        document.getElementById("input-threads").value = hw.physical_cores;

        // Verify and restrict GPU acceleration options
        if (!hw.has_nvidia) {
            document.getElementById("opt-cuda").disabled = true;
            document.getElementById("opt-cuda").innerText += " (Not Detected)";
        } else {
            appendLogLine("[SYSTEM] NVIDIA GPU with CUDA support detected. Native hardware acceleration active.");
        }
        
        if (!hw.has_vulkan) {
            document.getElementById("opt-vulkan").disabled = true;
            document.getElementById("opt-vulkan").innerText += " (Not Detected)";
        } else {
            appendLogLine("[SYSTEM] Vulkan graphics API support detected.");
        }
    } catch (e) {
        appendLogLine(`[WARNING] Hardware detection encountered an issue: ${e}. Using defaults.`, "error");
    }

    // B. Scan and store local models for both views
    try {
        scannedModelsMap = await api.scan_models();
        if (typeof loadBatchModels === 'function') {
            await loadBatchModels();
        } else if (typeof onCategoryChange === 'function') {
            onCategoryChange();
        }
    } catch (e) {
        appendLogLine(`[WARNING] Model scan failed: ${e}`, "error");
    }

    // C. Render Downloaded Local Models Library
    try {
        if (typeof renderLocalModelsLibrary === 'function') renderLocalModelsLibrary();
    } catch (e) {
        console.error("Failed to render local models library", e);
    }

    // D. Setup periodic polling loop for status using recursive setTimeout
    // Delayed start to let the UI settle first
    setTimeout(() => { 
        if (typeof pollServerStatus === 'function') pollServerStatus(); 
        if (typeof checkPipelineStatus === 'function') checkPipelineStatus();
    }, 1500);

    // Periodic check for Gateway and Atomic AI status every 15s
    setInterval(() => {
        if (typeof checkPipelineStatus === 'function') checkPipelineStatus();
    }, 15000);

    appendLogLine("[SYSTEM] AI Local Desktop inference suite is ready.");
}

// 2. Navigation Tabs switcher
function switchTab(tabId) {
    currentTab = tabId;
    
    // Buttons state
    document.getElementById("tab-control-btn").classList.toggle("active", tabId === 'control');
    document.getElementById("tab-download-btn").classList.toggle("active", tabId === 'download');
    
    // View state
    document.getElementById("view-control").classList.toggle("active", tabId === 'control');
    document.getElementById("view-download").classList.toggle("active", tabId === 'download');
}

async function openSystemFolder(type) {
    if (!api) return;
    try {
        await api.open_folder(type);
    } catch (e) {
        console.error("Failed to open directory", e);
    }
}

// Helper to append line to logs terminal directly
function appendLogLine(text, type = "system") {
    const terminal = document.getElementById("console-terminal");
    if (!terminal) return;
    const div = document.createElement("div");
    div.className = `console-line ${type}`;
    div.innerText = `[${new Date().toLocaleTimeString()}] ${text}`;
    terminal.appendChild(div);
    while (terminal.childElementCount > 120) {
        terminal.removeChild(terminal.firstElementChild);
    }
    if (terminalScrolledToBottom) {
        terminal.scrollTop = terminal.scrollHeight;
    }
}

// 3. Pipeline Connectivity Status Checker (Engine -> Gateway -> Atomic AI)
async function checkPipelineStatus() {
    const apiBase = window.BACKEND_API_BASE || "";
    
    // Check Engine (:8080 or active port)
    const dotEngine = document.getElementById("dot-engine");
    const lblEngine = document.getElementById("lbl-engine-status");
    const statusTextEl = document.getElementById("lbl-status-text");
    if (dotEngine && lblEngine) {
        const isRunning = statusTextEl && (statusTextEl.innerText === "RUNNING");
        dotEngine.style.background = isRunning ? "var(--accent-emerald)" : "#64748b";
        lblEngine.innerText = isRunning ? ":8080 (Active)" : ":8080 (Idle)";
    }

    // Check Gateway (:8082 / :8081)
    try {
        const gwRes = await fetch(apiBase + "/api/gateway/status").then(r => r.json()).catch(() => ({ reachable: false }));
        const dotGw = document.getElementById("dot-gateway");
        const lblGw = document.getElementById("lbl-gateway-status");
        if (dotGw && lblGw) {
            if (gwRes.reachable) {
                dotGw.style.background = gwRes.backend_healthy ? "var(--accent-emerald)" : "var(--accent-amber)";
                const portStr = gwRes.gateway_url ? gwRes.gateway_url.split(':').pop() : '8082';
                lblGw.innerText = `:${portStr} (${gwRes.backend_healthy ? 'Ready' : 'Standby'})`;
            } else {
                dotGw.style.background = "var(--accent-rose)";
                lblGw.innerText = "Offline";
            }
        }
    } catch (e) {
        console.warn("[Pipeline] Could not check Gateway status", e);
    }

    // Check Atomic AI Cognitive Proxy (:8000)
    try {
        const atRes = await fetch(apiBase + "/api/atomic/status").then(r => r.json()).catch(() => ({ reachable: false }));
        const dotAt = document.getElementById("dot-atomic");
        const lblAt = document.getElementById("lbl-atomic-status");
        if (dotAt && lblAt) {
            if (atRes.reachable) {
                dotAt.style.background = "var(--accent-emerald)";
                lblAt.innerText = ":8000 (Online)";
            } else {
                dotAt.style.background = "var(--accent-rose)";
                lblAt.innerText = "Offline";
            }
        }
    } catch (e) {
        console.warn("[Pipeline] Could not check Atomic AI status", e);
    }
}
