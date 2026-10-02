// manager.js - Control Dashboard and Server Management (Batch Runner & Hardware Orchestrator)

let currentBatchDetails = null;
let batchModelsList = [];
let currentModelRequestId = 0;
let isSyncing = false;

/**
 * Loads models hierarchically via api.scan_models_and_batches()
 * and populates the unified combobox #select-model-combo with "[Familia] — [Variante]".
 */
async function loadBatchModels() {
    if (!api) return;

    const select = document.getElementById("select-model-combo");
    if (!select) return;

    try {
        const res = await api.scan_models_and_batches();
        select.innerHTML = "";

        if (!res.success || !res.models || res.models.length === 0) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.disabled = true;
            opt.selected = true;
            opt.innerText = "No se encontraron modelos locales en /models/";
            select.appendChild(opt);

            // Add option for manual custom model path even when local models are empty
            const optCustom = document.createElement("option");
            optCustom.value = "CUSTOM";
            optCustom.innerText = "➕ Cargar ruta personalizada de archivo .gguf...";
            select.appendChild(optCustom);

            appendLogLine("[WARNING] No se encontraron modelos GGUF en el directorio de modelos.", "error");
            return;
        }

        batchModelsList = res.models;

        res.models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m.id;
            let label = m.concatenated_label;
            if (m.has_dedicated_binary) {
                label += " ⚡ [Dedicado]";
            }
            opt.innerText = label;
            select.appendChild(opt);
        });

        // Add option for manual custom model path
        const optCustom = document.createElement("option");
        optCustom.value = "CUSTOM";
        optCustom.innerText = "➕ Cargar ruta personalizada de archivo .gguf...";
        select.appendChild(optCustom);

        // Select the first valid model by default
        if (res.models.length > 0) {
            select.value = res.models[0].id;
            await onBatchModelChange();
        }
    } catch (e) {
        console.error("Failed to load batch models:", e);
        appendLogLine(`[ERROR] Error al escanear modelos y batches: ${e}`, "error");
    }
}

/**
 * Handles selection change in #select-model-combo.
 * Calls api.get_model_batch_details(modelId) to parse existing or auto-generate
 * calibrated .bat script and populate all UI configuration controls.
 */
async function onBatchModelChange() {
    const select = document.getElementById("select-model-combo");
    if (!select) return;
    const modelId = select.value;
    const requestId = ++currentModelRequestId;

    const customGroup = document.getElementById("custom-path-group");
    const batToggleRow = document.querySelector(".bat-editor-toggle-row");
    const batContainer = document.getElementById("bat-editor-container");
    const badge = document.getElementById("lbl-binary-badge");

    if (modelId === "CUSTOM") {
        if (customGroup) customGroup.style.display = "flex";
        if (batToggleRow) batToggleRow.style.display = "none";
        if (batContainer) batContainer.style.display = "none";
        if (badge) {
            badge.className = "binary-status-badge";
            badge.innerText = "Modo Ruta Personalizada";
        }
        currentBatchDetails = null;
        return;
    }

    if (customGroup) customGroup.style.display = "none";
    if (batToggleRow) batToggleRow.style.display = "block";

    if (badge) {
        badge.className = "binary-status-badge";
        badge.innerText = "Resolviendo binario y configuración...";
    }

    try {
        const details = await api.get_model_batch_details(modelId);
        // Guard against race conditions when user rapidly clicks through options
        if (requestId !== currentModelRequestId || select.value !== modelId) {
            return;
        }

        if (!details || !details.success) {
            appendLogLine(`[ERROR] No se pudo obtener la configuración del batch: ${details ? details.error : "Error desconocido"}`, "error");
            if (badge) {
                badge.className = "binary-status-badge";
                badge.innerText = "Error de configuración";
            }
            return;
        }

        currentBatchDetails = details;
        isSyncing = true;

        try {
            // Populate Core Parameters
            if (document.getElementById("input-port")) {
                document.getElementById("input-port").value = details.port || 8080;
            }
            if (document.getElementById("input-threads")) {
                document.getElementById("input-threads").value = details.threads || 8;
            }
            if (document.getElementById("input-context")) {
                document.getElementById("input-context").value = details.context || 8192;
            }
            if (document.getElementById("input-ngl")) {
                document.getElementById("input-ngl").value = details.ngl !== undefined ? details.ngl : 99;
            }

            // Flash Attention
            const checkFa = document.getElementById("check-flash-attn");
            if (checkFa) {
                checkFa.checked = details.flash_attn !== false;
            }

            // PolarQuant KV Cache Compression
            const checkPq = document.getElementById("check-pq-enable");
            const selectPq = document.getElementById("select-pq-mode");
            const modeGroup = document.getElementById("pq-mode-group");

            if (checkPq && selectPq && modeGroup) {
                if (details.cache_type_k && details.cache_type_k !== "f16" && details.cache_type_k !== "none") {
                    checkPq.checked = true;
                    modeGroup.style.display = "flex";

                    const ck = details.cache_type_k.toLowerCase();
                    if (ck.includes("q3_k")) {
                        selectPq.value = "4";
                    } else if (ck.includes("q4_0")) {
                        selectPq.value = "1";
                    } else if (ck.includes("q5_0")) {
                        selectPq.value = "5";
                    } else if (ck.includes("q6_k")) {
                        selectPq.value = "6";
                    } else if (ck.includes("q8_0")) {
                        selectPq.value = "2";
                    } else {
                        selectPq.value = "1";
                    }
                } else {
                    checkPq.checked = false;
                    modeGroup.style.display = "none";
                }
            }

            // Sampling Parameters
            if (document.getElementById("input-temp")) {
                document.getElementById("input-temp").value = details.temp !== undefined ? details.temp : 0.7;
            }
            if (document.getElementById("input-topp")) {
                document.getElementById("input-topp").value = details.top_p !== undefined ? details.top_p : 0.95;
            }
            if (document.getElementById("input-topk")) {
                document.getElementById("input-topk").value = details.top_k !== undefined ? details.top_k : 40;
            }
            if (document.getElementById("input-minp")) {
                document.getElementById("input-minp").value = details.min_p !== undefined ? details.min_p : 0.05;
            }

            // Vision Projector (mmproj) Display
            const mmprojInput = document.getElementById("input-mmproj");
            if (mmprojInput) {
                if (details.mmproj_file) {
                    mmprojInput.value = details.mmproj_file;
                } else if (details.model_info && details.model_info.mmproj && details.model_info.mmproj.length > 0) {
                    mmprojInput.value = details.model_info.mmproj[0].filename;
                } else {
                    mmprojInput.value = "None (Text LLM)";
                }
            }

            // Binary and Engine Resolution Status
            if (badge) {
                const bInfo = details.binary_info;
                if (bInfo && bInfo.success) {
                    if (bInfo.is_dedicated) {
                        badge.className = "binary-status-badge dedicated";
                        const modelName = (details.model_info && details.model_info.family) ? details.model_info.family : "Dedicado";
                        badge.innerText = `⚡ Dedicado (${modelName})`;
                        badge.title = `Binario dedicado: ${bInfo.binary_path}`;
                    } else {
                        badge.className = "binary-status-badge generic";
                        const bName = bInfo.build ? `${bInfo.binary_type} ${bInfo.build}` : bInfo.binary_type;
                        badge.innerText = `🚀 ${bName}`;
                        badge.title = `Binario genérico: ${bInfo.binary_path}`;
                    }

                    const selectEngine = document.getElementById("select-engine");
                    if (selectEngine && bInfo.binary_type) {
                        const mappedType = bInfo.binary_type === "CUSTOM_DEDICATED" ? "CUDA" : bInfo.binary_type;
                        selectEngine.value = mappedType;
                    }
                } else {
                    badge.className = "binary-status-badge";
                    badge.innerText = "Binario genérico";
                }
            }

            // Raw .BAT Script Editor Populate
            const lblBatFilename = document.getElementById("lbl-bat-filename");
            if (lblBatFilename) lblBatFilename.innerText = details.filename || "run.bat";

            const editorBat = document.getElementById("editor-bat-content");
            if (editorBat) editorBat.value = details.raw_content || "";

            const backupPill = document.getElementById("lbl-bat-backup-status");
            if (backupPill) {
                if (details.has_backup) {
                    backupPill.innerText = "Backup: .bat.bak existe";
                    backupPill.style.color = "var(--accent-emerald)";
                } else {
                    backupPill.innerText = "Auto-backup .bat.bak al guardar";
                    backupPill.style.color = "var(--accent-amber)";
                }
            }

            const saveResult = document.getElementById("lbl-bat-save-result");
            if (saveResult) saveResult.innerText = "";
        } finally {
            isSyncing = false;
        }

        const displayName = details.model_info ? details.model_info.concatenated_label : modelId;
        appendLogLine(`[SYSTEM] Modelo activo: ${displayName} [${details.filename}]`);
    } catch (e) {
        console.error("Error in onBatchModelChange:", e);
        appendLogLine(`[ERROR] Excepción cargando detalles de batch: ${e}`, "error");
    }
}

/**
 * Marks that there are pending unsaved changes in the batch script editor.
 */
function markBatPendingChanges() {
    const saveResult = document.getElementById("lbl-bat-save-result");
    if (saveResult) {
        saveResult.innerText = "● Cambios pendientes de guardar";
        saveResult.style.color = "var(--accent-amber)";
    }
}

/**
 * Synchronizes modifications from the UI parameter inputs into the raw .BAT editor textarea.
 */
function syncUItoBatEditor() {
    if (isSyncing) return;
    if (!currentBatchDetails) return;
    const editor = document.getElementById("editor-bat-content");
    if (!editor) return;

    let content = editor.value;
    if (!content) return;

    isSyncing = true;
    try {
        const port = document.getElementById("input-port") ? parseInt(document.getElementById("input-port").value) : null;
        const threads = document.getElementById("input-threads") ? parseInt(document.getElementById("input-threads").value) : null;
        const context = document.getElementById("input-context") ? parseInt(document.getElementById("input-context").value) : null;
        const ngl = document.getElementById("input-ngl") ? parseInt(document.getElementById("input-ngl").value) : null;
        const flashAttn = document.getElementById("check-flash-attn") ? document.getElementById("check-flash-attn").checked : null;
        const pqEnabled = document.getElementById("check-pq-enable") ? document.getElementById("check-pq-enable").checked : false;
        const pqMode = document.getElementById("select-pq-mode") ? document.getElementById("select-pq-mode").value : "1";
        const temp = document.getElementById("input-temp") ? parseFloat(document.getElementById("input-temp").value) : null;
        const topP = document.getElementById("input-topp") ? parseFloat(document.getElementById("input-topp").value) : null;
        const topK = document.getElementById("input-topk") ? parseInt(document.getElementById("input-topk").value) : null;
        const minP = document.getElementById("input-minp") ? parseFloat(document.getElementById("input-minp").value) : null;

        if (port && !isNaN(port)) {
            content = content.replace(/--port\s+\d+/, `--port          ${port}`);
            content = content.replace(/Puerto\s*:\s*\d+/, `Puerto : ${port}`);
            content = content.replace(/localhost:\d+/g, `localhost:${port}`);
        }
        if (context && !isNaN(context)) {
            if (/--ctx-size\s+\d+/.test(content)) {
                content = content.replace(/--ctx-size\s+\d+/, `--ctx-size      ${context}`);
            } else if (/-c\s+\d+/.test(content)) {
                content = content.replace(/-c\s+\d+/, `-c ${context}`);
            }
        }
        if (threads && !isNaN(threads)) {
            if (/--threads\s+\d+/.test(content)) {
                content = content.replace(/--threads\s+\d+/, `--threads       ${threads}`);
            } else if (/-t\s+\d+/.test(content)) {
                content = content.replace(/-t\s+\d+/, `-t ${threads}`);
            }
        }
        if (ngl !== null && !isNaN(ngl)) {
            if (/--n-gpu-layers\s+\d+/.test(content)) {
                content = content.replace(/--n-gpu-layers\s+\d+/, `--n-gpu-layers  ${ngl}`);
            } else if (/-ngl\s+\d+/.test(content)) {
                content = content.replace(/-ngl\s+\d+/, `-ngl ${ngl}`);
            }
        }
        if (flashAttn !== null) {
            const faVal = flashAttn ? "on" : "off";
            if (/--flash-attn\s+(on|off)/.test(content)) {
                content = content.replace(/--flash-attn\s+(on|off)/, `--flash-attn    ${faVal}`);
            } else if (/-fa\s+(on|off)/.test(content)) {
                content = content.replace(/-fa\s+(on|off)/, `-fa ${faVal}`);
            }
        }
        if (pqEnabled) {
            const pqMap = { "4": "q3_k", "1": "q4_0", "5": "q5_0", "6": "q6_k", "2": "q8_0" };
            const qType = pqMap[pqMode] || "q4_0";
            if (/--cache-type-k\s+[A-Za-z0-9_]+/.test(content)) {
                content = content.replace(/--cache-type-k\s+[A-Za-z0-9_]+/, `--cache-type-k  ${qType}`);
            }
            if (/--cache-type-v\s+[A-Za-z0-9_]+/.test(content)) {
                content = content.replace(/--cache-type-v\s+[A-Za-z0-9_]+/, `--cache-type-v  ${qType}`);
            }
        } else {
            if (/--cache-type-k\s+[A-Za-z0-9_]+/.test(content)) {
                content = content.replace(/--cache-type-k\s+[A-Za-z0-9_]+/, `--cache-type-k  f16`);
            }
            if (/--cache-type-v\s+[A-Za-z0-9_]+/.test(content)) {
                content = content.replace(/--cache-type-v\s+[A-Za-z0-9_]+/, `--cache-type-v  f16`);
            }
        }
        if (temp !== null && !isNaN(temp)) {
            content = content.replace(/--temp\s+[0-9.]+/, `--temp          ${temp}`);
        }
        if (topP !== null && !isNaN(topP)) {
            content = content.replace(/--top-p\s+[0-9.]+/, `--top-p         ${topP}`);
        }
        if (topK !== null && !isNaN(topK)) {
            content = content.replace(/--top-k\s+\d+/, `--top-k         ${topK}`);
        }
        if (minP !== null && !isNaN(minP)) {
            content = content.replace(/--min-p\s+[0-9.]+/, `--min-p         ${minP}`);
        }

        if (editor.value !== content) {
            editor.value = content;
            markBatPendingChanges();
        }
    } finally {
        isSyncing = false;
    }
}

/**
 * Synchronizes modifications typed directly into the raw .BAT textarea back into the UI controls.
 */
function syncBatEditorToUI() {
    if (isSyncing) return;
    const editor = document.getElementById("editor-bat-content");
    if (!editor) return;

    const content = editor.value;
    if (!content) return;

    isSyncing = true;
    try {
        const mPort = content.match(/--port\s+(\d+)/);
        if (mPort && document.getElementById("input-port")) {
            document.getElementById("input-port").value = parseInt(mPort[1]);
        }
        const mCtx = content.match(/--ctx-size\s+(\d+)/) || content.match(/-c\s+(\d+)/);
        if (mCtx && document.getElementById("input-context")) {
            document.getElementById("input-context").value = parseInt(mCtx[1]);
        }
        const mTh = content.match(/--threads\s+(\d+)/) || content.match(/-t\s+(\d+)/);
        if (mTh && document.getElementById("input-threads")) {
            document.getElementById("input-threads").value = parseInt(mTh[1]);
        }
        const mNgl = content.match(/--n-gpu-layers\s+(\d+)/) || content.match(/-ngl\s+(\d+)/);
        if (mNgl && document.getElementById("input-ngl")) {
            document.getElementById("input-ngl").value = parseInt(mNgl[1]);
        }
        const checkFa = document.getElementById("check-flash-attn");
        if (checkFa) {
            if (/--flash-attn\s+off|-fa\s+off/.test(content)) {
                checkFa.checked = false;
            } else if (/--flash-attn\s+on|-fa\s+on/.test(content)) {
                checkFa.checked = true;
            }
        }
        const checkPq = document.getElementById("check-pq-enable");
        const selectPq = document.getElementById("select-pq-mode");
        const modeGroup = document.getElementById("pq-mode-group");
        const mCk = content.match(/--cache-type-k\s+([A-Za-z0-9_]+)/);
        if (mCk && checkPq && selectPq) {
            const ck = mCk[1].toLowerCase();
            if (ck !== "f16" && ck !== "none") {
                checkPq.checked = true;
                if (modeGroup) modeGroup.style.display = "flex";
                if (ck.includes("q3_k")) selectPq.value = "4";
                else if (ck.includes("q4_0")) selectPq.value = "1";
                else if (ck.includes("q5_0")) selectPq.value = "5";
                else if (ck.includes("q6_k")) selectPq.value = "6";
                else if (ck.includes("q8_0")) selectPq.value = "2";
                else selectPq.value = "1";
            } else {
                checkPq.checked = false;
                if (modeGroup) modeGroup.style.display = "none";
            }
        }
        const mTemp = content.match(/--temp\s+([0-9.]+)/);
        if (mTemp && document.getElementById("input-temp")) {
            document.getElementById("input-temp").value = parseFloat(mTemp[1]);
        }
        const mTopp = content.match(/--top-p\s+([0-9.]+)/);
        if (mTopp && document.getElementById("input-topp")) {
            document.getElementById("input-topp").value = parseFloat(mTopp[1]);
        }
        const mTopk = content.match(/--top-k\s+(\d+)/);
        if (mTopk && document.getElementById("input-topk")) {
            document.getElementById("input-topk").value = parseInt(mTopk[1]);
        }
        const mMinp = content.match(/--min-p\s+([0-9.]+)/);
        if (mMinp && document.getElementById("input-minp")) {
            document.getElementById("input-minp").value = parseFloat(mMinp[1]);
        }

        markBatPendingChanges();
    } finally {
        isSyncing = false;
    }
}

/**
 * Toggles visibility of the raw .BAT editor textarea.
 */
function toggleBatEditor() {
    const container = document.getElementById("bat-editor-container");
    const chevron = document.getElementById("bat-editor-chevron");
    if (!container) return;

    if (container.style.display === "none" || !container.style.display) {
        container.style.display = "flex";
        if (chevron) chevron.innerText = "▲";
    } else {
        container.style.display = "none";
        if (chevron) chevron.innerText = "▼";
    }
}

/**
 * Persists changes in the raw .BAT textarea to disk with automatic .bat.bak backup.
 */
async function saveBatScript() {
    if (!api) return;

    if (!currentBatchDetails || !currentBatchDetails.path) {
        alert("No hay un script .bat cargado actualmente.");
        return;
    }

    // Ensure editor has latest UI values before saving
    syncUItoBatEditor();

    const editor = document.getElementById("editor-bat-content");
    const saveResult = document.getElementById("lbl-bat-save-result");
    if (!editor) return;

    const newContent = editor.value;
    if (saveResult) {
        saveResult.innerText = "Guardando...";
        saveResult.style.color = "var(--text-secondary)";
    }

    try {
        const res = await api.save_batch_script(currentBatchDetails.path, newContent, true);
        if (res.success) {
            currentBatchDetails.raw_content = newContent;
            currentBatchDetails.has_backup = true;
            if (res.parsed_config) {
                Object.assign(currentBatchDetails, res.parsed_config);
            }

            const backupPill = document.getElementById("lbl-bat-backup-status");
            if (backupPill) {
                backupPill.innerText = "Backup: .bat.bak existe";
                backupPill.style.color = "var(--accent-emerald)";
            }

            if (saveResult) {
                saveResult.innerText = "✅ Guardado exitoso con respaldo .bak";
                saveResult.style.color = "var(--accent-emerald)";
            }
            appendLogLine(`[SUCCESS] Script ${currentBatchDetails.filename} guardado con respaldo .bat.bak.`);
        } else {
            if (saveResult) {
                saveResult.innerText = `❌ Error: ${res.error}`;
                saveResult.style.color = "var(--accent-rose)";
            }
            appendLogLine(`[ERROR] Falló guardado de script: ${res.error}`, "error");
            alert(`Error al guardar script: ${res.error}`);
        }
    } catch (e) {
        if (saveResult) {
            saveResult.innerText = `❌ Excepción: ${e}`;
            saveResult.style.color = "var(--accent-rose)";
        }
        appendLogLine(`[ERROR] Excepción al guardar script batch: ${e}`, "error");
    }
}

/**
 * Reloads all models across the Dashboard combobox and Download Library table.
 */
async function reloadModelDropdown() {
    if (!api) return;
    try {
        scannedModelsMap = await api.scan_models();
        await loadBatchModels();
        if (typeof renderLocalModelsLibrary === "function") {
            renderLocalModelsLibrary();
        }
        appendLogLine("[SYSTEM] Modelos locales recargados y sincronizados.");
    } catch (e) {
        console.error("Failed to reload models:", e);
        appendLogLine(`[ERROR] Fallo al recargar modelos: ${e}`, "error");
    }
}

/**
 * Legacy compatibility stubs for category dropdown and custom model changes.
 */
function onCategoryChange() {
    // Kept for backward compatibility
}

function onModelSelectChange() {
    // Kept for backward compatibility
}

/**
 * Hardware and Parameter Optimization Reactive Handler
 */
async function onEngineOrPqChange() {
    if (!api) return;

    const engine = document.getElementById("select-engine").value;
    const pq_enabled = document.getElementById("check-pq-enable").checked;
    const pq_choice = pq_enabled ? document.getElementById("select-pq-mode").value : "3";

    if (currentBatchDetails) {
        // In Batch Runner mode, preserve model-calibrated context/ngl, only sync KV cache compression
        syncUItoBatEditor();
        return;
    }

    try {
        const params = await api.get_optimized_params(engine, pq_choice);
        document.getElementById("input-context").value = params.context;
        document.getElementById("input-ngl").value = params.ngl;
        document.getElementById("input-threads").value = params.threads;
        appendLogLine(`[SYSTEM] Parámetros sugeridos para [${engine}] (PQ ${pq_choice}): ctx=${params.context}, ngl=${params.ngl}, threads=${params.threads}.`);
    } catch (e) {
        console.error("Optimization failed:", e);
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

/**
 * Lifecycle Control: Starts or stops the inference server.
 * Prioritizes direct execution of the calibrated .bat script.
 */
async function toggleServer() {
    if (!api) return;

    const statusText = document.getElementById("lbl-status-text").innerText;

    if (statusText === "STOPPED") {
        const combo = document.getElementById("select-model-combo");
        const comboVal = combo ? combo.value : "";

        if (comboVal === "CUSTOM") {
            // Manual path execution fallback
            const modelPath = document.getElementById("input-custom-model").value.trim();
            if (!modelPath) {
                appendLogLine("[ERROR] Debes ingresar una ruta válida de archivo .gguf.", "error");
                alert("Por favor ingresa una ruta válida hacia un modelo .gguf.");
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

            const modelFilename = modelPath.split("\\").pop().split("/").pop();
            appendLogLine(`[SYSTEM] Iniciando servidor para modelo manual: ${modelFilename}`);
            setButtonState("loading");

            try {
                const res = await api.start_server(uiConfig);
                if (res.success) {
                    appendLogLine(`[SYSTEM] ${res.message}`);
                } else {
                    appendLogLine(`[ERROR] Falló inicio del subproceso: ${res.message}`, "error");
                    alert(res.message);
                    setButtonState("stopped");
                }
            } catch (e) {
                appendLogLine(`[ERROR] Excepción al iniciar servidor: ${e}`, "error");
                setButtonState("stopped");
            }
        } else if (currentBatchDetails && currentBatchDetails.path) {
            // Orchestrated Batch Runner flow
            // 1. Sync any modified UI parameters to editor
            syncUItoBatEditor();

            const editor = document.getElementById("editor-bat-content");
            const editorContent = editor ? editor.value : currentBatchDetails.raw_content;

            // 2. Auto-save if there are unsaved modifications so the executed .bat runs with user settings
            if (editorContent && editorContent !== currentBatchDetails.raw_content) {
                try {
                    const saveRes = await api.save_batch_script(currentBatchDetails.path, editorContent, true);
                    if (saveRes.success) {
                        currentBatchDetails.raw_content = editorContent;
                        currentBatchDetails.has_backup = true;
                        if (saveRes.parsed_config) {
                            Object.assign(currentBatchDetails, saveRes.parsed_config);
                        }
                    }
                } catch (saveErr) {
                    console.warn("Auto-save before launch encountered an error:", saveErr);
                }
            }

            const port = parseInt(document.getElementById("input-port").value) || currentBatchDetails.port || 8080;
            const modelLabel = currentBatchDetails.model_info ? currentBatchDetails.model_info.concatenated_label : currentBatchDetails.filename;

            appendLogLine(`[SYSTEM] Lanzando script .bat: ${currentBatchDetails.filename} (${modelLabel}) en puerto ${port}...`);
            setButtonState("loading");

            try {
                const res = await api.launch_batch_script(currentBatchDetails.path, port);
                if (res.success) {
                    appendLogLine(`[SYSTEM] ${res.message}`);
                } else {
                    appendLogLine(`[ERROR] Falló inicio de script batch: ${res.message}`, "error");
                    alert(res.message);
                    setButtonState("stopped");
                }
            } catch (e) {
                appendLogLine(`[ERROR] Excepción de conexión al lanzar script: ${e}`, "error");
                setButtonState("stopped");
            }
        } else {
            alert("Por favor selecciona un modelo válido.");
        }
    } else {
        // Stop flow
        appendLogLine("[SYSTEM] Enviando señal de apagado al proceso servidor...");
        try {
            const res = await api.stop_server();
            appendLogLine(`[SYSTEM] ${res.message}`);
        } catch (e) {
            appendLogLine(`[ERROR] Error al detener servidor: ${e}`, "error");
        }
    }
}

/**
 * Sets button state and icon dynamically.
 */
function setButtonState(state) {
    const btn = document.getElementById("btn-toggle-server");
    const text = document.getElementById("btn-text");
    if (!btn || !text) return;

    btn.className = "btn-primary";

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

/**
 * Polling loop monitoring server status and logs.
 * Includes circular buffer capping to 120 lines in #console-terminal
 * to prevent DOM memory leaks in pywebview / WebView2.
 */
async function pollServerStatus() {
    if (!api) return;
    if (isPolling) return;
    isPolling = true;

    try {
        const info = await api.get_server_status();

        const badge = document.getElementById("service-status-badge");
        const statusText = document.getElementById("lbl-status-text");

        if (badge && statusText) {
            badge.className = "status-badge";

            if (info.status === "STOPPED") {
                badge.classList.add("stopped");
                statusText.innerText = "STOPPED";
                setButtonState("stopped");
                const openBtn = document.getElementById("btn-open-webui");
                if (openBtn) openBtn.disabled = true;
                const activeModelLbl = document.getElementById("lbl-active-model");
                if (activeModelLbl) activeModelLbl.innerText = "None (Server inactive)";
            } else if (info.status === "LOADING") {
                badge.classList.add("loading");
                statusText.innerText = "LOADING";
                setButtonState("loading");
                const openBtn = document.getElementById("btn-open-webui");
                if (openBtn) openBtn.disabled = true;
                const activeModelLbl = document.getElementById("lbl-active-model");
                if (activeModelLbl) activeModelLbl.innerText = info.model || "Loading...";
            } else if (info.status === "RUNNING") {
                badge.classList.add("running");
                statusText.innerText = "RUNNING";
                setButtonState("running");
                const openBtn = document.getElementById("btn-open-webui");
                if (openBtn) openBtn.disabled = false;
                const activeModelLbl = document.getElementById("lbl-active-model");
                if (activeModelLbl) activeModelLbl.innerText = info.model;
            }
        }

        const endpointEl = document.getElementById("lbl-endpoint");
        if (endpointEl) {
            endpointEl.innerText = `http://localhost:${info.port}`;
        }

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

                    // Circular capping to 120 lines
                    while (terminal.childElementCount > 120) {
                        terminal.removeChild(terminal.firstElementChild);
                    }

                    if (terminalScrolledToBottom) {
                        terminal.scrollTop = terminal.scrollHeight;
                    }
                }
            }
        }

    } catch (e) {
        console.error("Poller error:", e);
    } finally {
        isPolling = false;
        logPoller = setTimeout(pollServerStatus, 2500);
    }
}

function copyEndpoint() {
    const text = document.getElementById("lbl-endpoint").innerText;
    navigator.clipboard.writeText(text).then(() => {
        appendLogLine(`[SYSTEM] Endpoint copiado al portapapeles: ${text}`);
    }).catch(err => {
        console.error("Clipboard copy failed:", err);
    });
}

function openWebUI() {
    const port = document.getElementById("input-port").value || 8080;
    window.open(`http://localhost:${port}`);
}

/**
 * Binds input and change event listeners across UI configuration inputs
 * and the raw batch script editor to ensure real-time bidirectional synchronization.
 */
function initBatchUIEvents() {
    const inputs = [
        "input-port", "input-threads", "input-context", "input-ngl",
        "check-flash-attn", "input-temp", "input-topp", "input-topk", "input-minp"
    ];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", syncUItoBatEditor);
            el.addEventListener("change", syncUItoBatEditor);
        }
    });

    const editor = document.getElementById("editor-bat-content");
    if (editor) {
        editor.addEventListener("input", syncBatEditorToUI);
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initBatchUIEvents);
} else {
    initBatchUIEvents();
}

