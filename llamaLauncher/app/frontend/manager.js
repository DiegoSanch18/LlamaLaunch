// manager.js - Control Dashboard and Server Management

// Dropdown scanners with category filtering (EDGE, LARGE, CODER)
function onCategoryChange() {
    const selectCat = document.getElementById("select-category");
    if (!selectCat) return;
    const category = selectCat.value;
    
    const select = document.getElementById("select-model");
    if (!select) return;
    select.innerHTML = ""; // Clear
    
    if (!scannedModelsMap) {
        console.warn("[SYSTEM] scannedModelsMap not initialized yet.");
        return;
    }
    
    const list = scannedModelsMap[category] || [];
    let hasModels = false;

    if (list && list.length > 0) {
        hasModels = true;
        list.forEach(model => {
            const opt = document.createElement("option");
            opt.value = model.absolute_path;
            opt.innerText = model.filename;
            select.appendChild(opt);
        });
    }
    
    if (!hasModels) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.disabled = true;
        opt.selected = true;
        opt.innerText = `No local .gguf files found under /models/${category}/`;
        select.appendChild(opt);
    }

    // Always add option for custom drag & drop path at the bottom
    const optCustom = document.createElement("option");
    optCustom.value = "CUSTOM";
    optCustom.innerText = "➕ Load custom .gguf file path...";
    select.appendChild(optCustom);
    
    // Trigger select change handler to show custom input if needed
    onModelSelectChange();
}

async function reloadModelDropdown() {
    if (!api) return;
    try {
        scannedModelsMap = await api.scan_models();
        onCategoryChange();
        if (typeof renderLocalModelsLibrary === 'function') renderLocalModelsLibrary();
    } catch (e) {
        console.error("Failed to reload models after download", e);
    }
}

function onModelSelectChange() {
    const val = document.getElementById("select-model").value;
    const customGroup = document.getElementById("custom-path-group");
    if (val === "CUSTOM") {
        customGroup.style.display = "flex";
    } else {
        customGroup.style.display = "none";
    }
}

// Hardware and Parameter Optimization Reactive Handler
async function onEngineOrPqChange() {
    if (!api) return;
    
    const engine = document.getElementById("select-engine").value;
    const pq_enabled = document.getElementById("check-pq-enable").checked;
    const pq_choice = pq_enabled ? document.getElementById("select-pq-mode").value : "3";
    
    try {
        const params = await api.get_optimized_params(engine, pq_choice);
        
        // Automatically suggest optimization results
        document.getElementById("input-context").value = params.context;
        document.getElementById("input-ngl").value = params.ngl;
        document.getElementById("input-threads").value = params.threads;
        
        appendLogLine(`[SYSTEM] Parameters optimized for [${engine}] with KV cache compression [Level ${pq_choice}]. Sug: ctx=${params.context}, ngl=${params.ngl}.`);
    } catch (e) {
        console.error("Optimization failed", e);
    }
}

function onPqCheckboxChange() {
    const enabled = document.getElementById("check-pq-enable").checked;
    const modeGroup = document.getElementById("pq-mode-group");
    if (enabled) {
        modeGroup.style.display = "flex";
    } else {
        modeGroup.style.display = "none";
    }
    onEngineOrPqChange();
}

// Lifecyle Control: Start and Stop llama-server
async function toggleServer() {
    if (!api) return;

    const btn = document.getElementById("btn-toggle-server");
    const statusText = document.getElementById("lbl-status-text").innerText;

    if (statusText === "STOPPED") {
        // Start flow
        let modelPath = document.getElementById("select-model").value;
        if (modelPath === "CUSTOM") {
            modelPath = document.getElementById("input-custom-model").value.trim();
        }

        if (!modelPath) {
            appendLogLine("[ERROR] You must select a model or input a valid .gguf path.", "error");
            alert("Please select a valid .gguf model file to proceed.");
            return;
        }

        const uiConfig = {
            engine: document.getElementById("select-engine").value,
            model_path: modelPath,
            port: parseInt(document.getElementById("input-port").value) || 8080,
            threads: parseInt(document.getElementById("input-threads").value) || 4,
            context: parseInt(document.getElementById("input-context").value) || 4096,
            ngl: parseInt(document.getElementById("input-ngl").value) || 0,
            pq_choice: document.getElementById("check-pq-enable").checked ? document.getElementById("select-pq-mode").value : "3",
            context_shift: document.getElementById("check-shift").checked
        };

        const modelFilename = modelPath.split('\\').pop().split('/').pop();
        appendLogLine(`[SYSTEM] Requesting server startup for model: ${modelFilename}`);
        setButtonState("loading");

        try {
            const res = await api.start_server(uiConfig);
            if (res.success) {
                appendLogLine(`[SYSTEM] ${res.message}`);
            } else {
                appendLogLine(`[ERROR] Failed to start subprocess: ${res.message}`, "error");
                alert(res.message);
                setButtonState("stopped");
            }
        } catch (e) {
            appendLogLine(`[ERROR] Network/bridge exception on start: ${e}`, "error");
            setButtonState("stopped");
        }
    } else {
        // Stop flow
        appendLogLine("[SYSTEM] Sending shutdown signal to llama-server subprocess...");
        try {
            const res = await api.stop_server();
            appendLogLine(`[SYSTEM] ${res.message}`);
        } catch (e) {
            appendLogLine(`[ERROR] Failed to stop server process: ${e}`, "error");
        }
    }
}

// Set status button appearance dynamically
function setButtonState(state) {
    const btn = document.getElementById("btn-toggle-server");
    const text = document.getElementById("btn-text");
    
    btn.className = "btn-primary"; // Reset

    if (state === "loading") {
        btn.classList.add("loading");
        btn.disabled = true;
        text.innerText = "LOADING MODEL...";
        btn.querySelector(".btn-icon").innerText = "⏳";
    } else if (state === "running") {
        btn.classList.add("stop");
        btn.disabled = false;
        text.innerText = "STOP SERVER";
        btn.querySelector(".btn-icon").innerText = "⏹";
    } else {
        btn.classList.add("start");
        btn.disabled = false;
        text.innerText = "START SERVER";
        btn.querySelector(".btn-icon").innerText = "▶";
    }
}

// Polling Loops: Monitoring Server Logs and Health status (Recursive setTimeout)
// Uses isPolling guard to prevent concurrent API calls from stacking up
// and saturating the pywebview JS<->Python bridge.
async function pollServerStatus() {
    if (!api) return;
    if (isPolling) return; // Prevent concurrent polls from stacking
    isPolling = true;

    try {
        const info = await api.get_server_status();
        
        // A. Update Status badges
        const badge = document.getElementById("service-status-badge");
        const statusText = document.getElementById("lbl-status-text");
        
        if (badge) {
            badge.className = "status-badge"; // Reset classes
            
            if (info.status === "STOPPED") {
                badge.classList.add("stopped");
                statusText.innerText = "STOPPED";
                setButtonState("stopped");
                document.getElementById("btn-open-webui").disabled = true;
                document.getElementById("lbl-active-model").innerText = "None (Server inactive)";
            } else if (info.status === "LOADING") {
                badge.classList.add("loading");
                statusText.innerText = "LOADING";
                setButtonState("loading");
                document.getElementById("btn-open-webui").disabled = true;
                document.getElementById("lbl-active-model").innerText = info.model || "Loading...";
            } else if (info.status === "RUNNING") {
                badge.classList.add("running");
                statusText.innerText = "RUNNING";
                setButtonState("running");
                document.getElementById("btn-open-webui").disabled = false;
                document.getElementById("lbl-active-model").innerText = info.model;
            }
        }

        // B. Update endpoint displays
        const endpointEl = document.getElementById("lbl-endpoint");
        if (endpointEl) {
            endpointEl.innerText = `http://localhost:${info.port}`;
        }

        // C. Update logs terminal panel ONLY when server is LOADING or RUNNING
        // When STOPPED, preserve manually appended init/system messages
        if (info.status !== "STOPPED") {
            const logContentString = info.logs.join("\n");
            if (logContentString !== lastLogText) {
                lastLogText = logContentString;
                const terminal = document.getElementById("console-terminal");
                
                if (terminal) {
                    terminal.innerHTML = "";
                    info.logs.forEach(line => {
                        let typeClass = "";
                        if (line.includes("[ERROR]") || line.includes("error:")) {
                            typeClass = "error";
                        } else if (line.includes("[SYSTEM]") || line.includes("[INFO]")) {
                            typeClass = "system";
                        } else if (line.includes("[SUCCESS]")) {
                            typeClass = "success";
                        }
                        
                        const lineDiv = document.createElement("div");
                        lineDiv.className = `console-line ${typeClass}`;
                        lineDiv.innerText = line;
                        terminal.appendChild(lineDiv);
                    });
                    
                    // Auto scroll to bottom if user is not reviewing previous history
                    if (terminalScrolledToBottom) {
                        terminal.scrollTop = terminal.scrollHeight;
                    }
                }
            }
        }

    } catch (e) {
        console.error("Poller error", e);
    } finally {
        isPolling = false;
        // Schedule next poll 2.5 seconds after completion to reduce bridge pressure
        logPoller = setTimeout(pollServerStatus, 2500);
    }
}

function copyEndpoint() {
    const text = document.getElementById("lbl-endpoint").innerText;
    navigator.clipboard.writeText(text).then(() => {
        appendLogLine(`[SYSTEM] API Endpoint copied to clipboard: ${text}`);
    }).catch(err => {
        console.error("Clipboard copy failed", err);
    });
}

function openWebUI() {
    const port = document.getElementById("input-port").value || 8080;
    window.open(`http://localhost:${port}`);
}
