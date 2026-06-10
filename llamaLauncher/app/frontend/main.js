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

// 1. Wait for pywebview bridge initialization
window.addEventListener('pywebviewready', () => {
    api = window.pywebview.api;
    initApp();
});

// Fallback if not running inside pywebview (debugging)
window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (!api) {
            console.warn("[SYSTEM] 'pywebview' communication bridge not detected. Running in standalone browser mock mode.");
        }
    }, 2000);
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

    // B. Scan and store local models (then trigger initial category rendering)
    try {
        scannedModelsMap = await api.scan_models();
        if (typeof onCategoryChange === 'function') onCategoryChange();
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
    }, 1500);

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
    if (terminalScrolledToBottom) {
        terminal.scrollTop = terminal.scrollHeight;
    }
}
