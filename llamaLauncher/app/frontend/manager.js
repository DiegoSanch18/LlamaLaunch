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
                    if (ck.includes("iq4_nl")) {
                        selectPq.value = "iq4_nl";
                    } else if (ck.includes("q4_0")) {
                        selectPq.value = "q4_0";
                    } else if (ck.includes("q5_0")) {
                        selectPq.value = "q5_0";
                    } else if (ck.includes("q8_0")) {
                        selectPq.value = "q8_0";
                    } else {
                        selectPq.value = "iq4_nl";
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

            // Vision Projector (mmproj) Checkbox State
            const checkVision = document.getElementById("check-vision");
            const lblVision = document.getElementById("lbl-vision-file");

            let visionFile = "";
            if (details.model_info && details.model_info.mmproj && details.model_info.mmproj.length > 0) {
                visionFile = details.model_info.mmproj[0].filename;
            } else if (details.available_mmproj) {
                visionFile = details.available_mmproj;
            } else if (details.mmproj_file && details.mmproj_file.trim() !== "" && details.mmproj_file !== "None") {
                visionFile = details.mmproj_file;
            }

            if (checkVision && lblVision) {
                if (visionFile) {
                    checkVision.disabled = false;
                    checkVision.dataset.availableFile = visionFile;
                    const isVisionActive = !!(details.mmproj_file && details.mmproj_file.trim() !== "" && details.mmproj_file !== "None");
                    checkVision.checked = isVisionActive;
                    if (isVisionActive) {
                        lblVision.innerText = `(${visionFile})`;
                        lblVision.style.color = "var(--accent-emerald)";
                    } else {
                        lblVision.innerText = `(${visionFile} — Desactivado)`;
                        lblVision.style.color = "var(--text-muted)";
                    }
                } else {
                    checkVision.disabled = true;
                    checkVision.checked = false;
                    checkVision.dataset.availableFile = "";
                    lblVision.innerText = "(No disponible)";
                    lblVision.style.color = "var(--text-muted)";
                }
            }

            // Multi Token Prediction (MTP) Checkbox State
            const checkMtp = document.getElementById("check-mtp");
            const lblMtp = document.getElementById("lbl-mtp-file");

            let mtpFile = "";
            if (details.model_info && details.model_info.mtp && details.model_info.mtp.length > 0) {
                mtpFile = details.model_info.mtp[0].filename;
            } else if (details.available_mtp) {
                mtpFile = details.available_mtp;
            } else if (details.spec_draft_model && details.spec_draft_model.trim() !== "" && details.spec_draft_model !== "None" && !details.spec_draft_model.includes("%")) {
                mtpFile = details.spec_draft_model;
            }

            if (checkMtp && lblMtp) {
                if (mtpFile) {
                    checkMtp.disabled = false;
                    checkMtp.dataset.availableFile = mtpFile;
                    const isMtpActive = !!(details.spec_draft_model && details.spec_draft_model.trim() !== "" && details.spec_draft_model !== "None" && (details.spec_type === "draft-mtp" || details.mtp_enabled));
                    checkMtp.checked = isMtpActive;
                    if (isMtpActive) {
                        lblMtp.innerText = `(${mtpFile})`;
                        lblMtp.style.color = "var(--accent-emerald)";
                    } else {
                        lblMtp.innerText = `(${mtpFile} — Desactivado)`;
                        lblMtp.style.color = "var(--text-muted)";
                    }
                } else {
                    checkMtp.disabled = true;
                    checkMtp.checked = false;
                    checkMtp.dataset.availableFile = "";
                    lblMtp.innerText = "(No disponible)";
                    lblMtp.style.color = "var(--text-muted)";
                }
            }

            // Binary and Engine Resolution Status
            const selectEngine = document.getElementById("select-engine");
            const engineVal = details.engine || (details.ngl === 0 ? "CPU" : ((details.binary_info && details.binary_info.binary_type === "CUSTOM_DEDICATED") ? "CUDA" : (details.binary_info ? details.binary_info.binary_type : "CUDA")));
            if (selectEngine) {
                selectEngine.value = engineVal;
            }
            handleEngineUI(engineVal);

            // Raw Configuration Editor Populate (.json / .bat)
            const lblBatFilename = document.getElementById("lbl-bat-filename");
            if (lblBatFilename) lblBatFilename.innerText = details.filename || "config.json";

            const editorBat = document.getElementById("editor-bat-content");
            if (editorBat) editorBat.value = details.raw_content || "";

            const backupPill = document.getElementById("lbl-bat-backup-status");
            if (backupPill) {
                const ext = (details.filename && details.filename.endsWith(".json")) ? ".json" : ".bat";
                if (details.has_backup) {
                    backupPill.innerText = `Backup: ${ext}.bak existe`;
                    backupPill.style.color = "var(--accent-emerald)";
                } else {
                    backupPill.innerText = `Auto-backup ${ext}.bak al guardar`;
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
 * Updates UI controls (NGL, Flash Attention, Badges) based on selected Execution Engine.
 * When CPU is selected, sets GPU layers (NGL) to 0 and disables the input.
 */
function handleEngineUI(engine) {
    const inputNgl = document.getElementById("input-ngl");
    const checkFa = document.getElementById("check-flash-attn");
    const checkPq = document.getElementById("check-pq-enable");
    const badge = document.getElementById("lbl-binary-badge");

    if (engine === "CPU") {
        if (inputNgl) {
            const currentVal = parseInt(inputNgl.value);
            if (!isNaN(currentVal) && currentVal > 0) {
                inputNgl.dataset.prevNgl = currentVal;
            }
            inputNgl.value = 0;
            inputNgl.disabled = true;
            inputNgl.title = "En modo CPU las capas GPU se desactivan (0)";
        }
        if (checkFa) {
            checkFa.disabled = false;
            checkFa.title = "Flash Attention (aceleración AVX2 y soporte obligatorio para KV Cache cuantizado)";
            if (checkPq && checkPq.checked) {
                checkFa.checked = true;
            }
        }
        if (badge) {
            badge.className = "binary-status-badge cpu";
            badge.innerText = "💻 CPU Universal (b9283 / AVX2)";
            badge.title = "Inferencia pura en procesador del sistema sin offload GPU";
        }
    } else {
        if (inputNgl) {
            inputNgl.disabled = false;
            inputNgl.title = "";
            const restored = inputNgl.dataset.prevNgl || (currentBatchDetails ? (currentBatchDetails.ngl || 99) : 99);
            if (parseInt(inputNgl.value) === 0) {
                inputNgl.value = restored;
            }
        }
        if (checkFa) {
            checkFa.disabled = false;
            checkFa.title = "";
            if (checkPq && checkPq.checked) {
                checkFa.checked = true;
            } else {
                checkFa.checked = (engine === "CUDA");
            }
        }
        if (badge) {
            if (engine === "VULKAN") {
                badge.className = "binary-status-badge vulkan";
                badge.innerText = "⚡ Vulkan b9297";
                badge.title = "Aceleración gráfica Vulkan (AMD / Intel / Generic)";
            } else {
                if (currentBatchDetails && currentBatchDetails.binary_info && currentBatchDetails.binary_info.is_dedicated) {
                    badge.className = "binary-status-badge dedicated";
                    const modelName = (currentBatchDetails.model_info && currentBatchDetails.model_info.family) ? currentBatchDetails.model_info.family : "Dedicado";
                    badge.innerText = `⚡ Dedicado (${modelName})`;
                    badge.title = `Binario dedicado: ${currentBatchDetails.binary_info.binary_path}`;
                } else {
                    badge.className = "binary-status-badge generic";
                    badge.innerText = "🚀 CUDA b9297";
                    badge.title = "Aceleración NVIDIA CUDA con Flash Attention";
                }
            }
        }
    }
}

/**
 * Reacts to user toggling the Vision (mmproj) checkbox.
 * Enables or disables multimodal projector flag in the configuration.
 */
function onVisionCheckboxChange() {
    const checkVision = document.getElementById("check-vision");
    const lblVision = document.getElementById("lbl-vision-file");
    const checkMtp = document.getElementById("check-mtp");
    const lblMtp = document.getElementById("lbl-mtp-file");
    if (!checkVision || !lblVision) return;

    const availableFile = checkVision.dataset.availableFile || "";
    if (checkVision.checked) {
        // Enforce llama.cpp restriction: mmproj and MTP are mutually exclusive
        if (checkMtp && checkMtp.checked) {
            checkMtp.checked = false;
            const mtpFile = checkMtp.dataset.availableFile || "";
            if (lblMtp) {
                lblMtp.innerText = mtpFile ? `(${mtpFile} — Desactivado por Vision)` : "(Desactivado por Vision)";
                lblMtp.style.color = "var(--text-muted)";
            }
            if (currentBatchDetails) {
                currentBatchDetails.spec_type = "";
                currentBatchDetails.spec_draft_model = "";
                currentBatchDetails.mtp_enabled = false;
            }
        }

        lblVision.innerText = availableFile ? `(${availableFile})` : "(Activo)";
        lblVision.style.color = "var(--accent-emerald)";
        if (currentBatchDetails) {
            currentBatchDetails.mmproj_file = availableFile;
        }
    } else {
        lblVision.innerText = availableFile ? `(${availableFile} — Desactivado)` : "(Desactivado)";
        lblVision.style.color = "var(--text-muted)";
        if (currentBatchDetails) {
            currentBatchDetails.mmproj_file = "";
        }
    }
    syncUItoBatEditor();
}

/**
 * Reacts to user toggling the Multi Token Prediction (MTP) checkbox.
 * Enables or disables speculative draft model flags in the configuration.
 */
function onMtpCheckboxChange() {
    const checkMtp = document.getElementById("check-mtp");
    const lblMtp = document.getElementById("lbl-mtp-file");
    const checkVision = document.getElementById("check-vision");
    const lblVision = document.getElementById("lbl-vision-file");
    if (!checkMtp || !lblMtp) return;

    const availableFile = checkMtp.dataset.availableFile || "";
    if (checkMtp.checked) {
        // Enforce llama.cpp restriction: MTP and mmproj are mutually exclusive
        if (checkVision && checkVision.checked) {
            checkVision.checked = false;
            const visFile = checkVision.dataset.availableFile || "";
            if (lblVision) {
                lblVision.innerText = visFile ? `(${visFile} — Desactivado por MTP)` : "(Desactivado por MTP)";
                lblVision.style.color = "var(--text-muted)";
            }
            if (currentBatchDetails) {
                currentBatchDetails.mmproj_file = "";
            }
        }

        lblMtp.innerText = availableFile ? `(${availableFile})` : "(Activo)";
        lblMtp.style.color = "var(--accent-emerald)";
        if (currentBatchDetails) {
            currentBatchDetails.spec_type = "draft-mtp";
            currentBatchDetails.spec_draft_model = availableFile;
            currentBatchDetails.mtp_enabled = true;
        }
    } else {
        lblMtp.innerText = availableFile ? `(${availableFile} — Desactivado)` : "(Desactivado)";
        lblMtp.style.color = "var(--text-muted)";
        if (currentBatchDetails) {
            currentBatchDetails.spec_type = "";
            currentBatchDetails.spec_draft_model = "";
            currentBatchDetails.mtp_enabled = false;
        }
    }
    syncUItoBatEditor();
}

/**
 * Synchronizes modifications from the UI parameter inputs into the raw .BAT or .JSON editor textarea.
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
        const pqEnabled = document.getElementById("check-pq-enable") ? document.getElementById("check-pq-enable").checked : false;
        let flashAttn = document.getElementById("check-flash-attn") ? document.getElementById("check-flash-attn").checked : null;
        if (pqEnabled) {
            flashAttn = true;
            const checkFa = document.getElementById("check-flash-attn");
            if (checkFa && !checkFa.checked) checkFa.checked = true;
        }
        const pqMode = document.getElementById("select-pq-mode") ? document.getElementById("select-pq-mode").value : "1";
        const temp = document.getElementById("input-temp") ? parseFloat(document.getElementById("input-temp").value) : null;
        const topP = document.getElementById("input-topp") ? parseFloat(document.getElementById("input-topp").value) : null;
        const topK = document.getElementById("input-topk") ? parseInt(document.getElementById("input-topk").value) : null;
        const minP = document.getElementById("input-minp") ? parseFloat(document.getElementById("input-minp").value) : null;
        const engine = document.getElementById("select-engine") ? document.getElementById("select-engine").value : "CUDA";
        const checkVision = document.getElementById("check-vision");
        const visionEnabled = checkVision ? checkVision.checked : false;
        const availableMmproj = checkVision ? (checkVision.dataset.availableFile || "") : "";
        const mmprojFile = (visionEnabled && availableMmproj) ? availableMmproj : "";

        const checkMtp = document.getElementById("check-mtp");
        const mtpEnabled = checkMtp ? checkMtp.checked : false;
        const availableMtp = checkMtp ? (checkMtp.dataset.availableFile || "") : "";
        const mtpFile = (mtpEnabled && availableMtp) ? availableMtp : "";

        // JSON format synchronization
        if (content.trim().startsWith("{")) {
            try {
                const jsonObj = JSON.parse(content);
                if (port && !isNaN(port)) jsonObj.port = port;
                if (context && !isNaN(context)) jsonObj.context = context;
                if (threads && !isNaN(threads)) jsonObj.threads = threads;
                if (ngl !== null && !isNaN(ngl)) jsonObj.ngl = ngl;
                jsonObj.engine = engine;
                jsonObj.mmproj_file = mmprojFile;
                if (mtpEnabled && mtpFile) {
                    jsonObj.spec_type = "draft-mtp";
                    jsonObj.spec_draft_model = mtpFile;
                    jsonObj.spec_draft_n_max = jsonObj.spec_draft_n_max || 2;
                    jsonObj.spec_draft_p_min = jsonObj.spec_draft_p_min || 0.5;
                    jsonObj.n_gpu_layers_draft = jsonObj.n_gpu_layers_draft || "all";
                } else {
                    jsonObj.spec_type = "";
                    jsonObj.spec_draft_model = "";
                }
                if (flashAttn !== null) jsonObj.flash_attn = flashAttn;
                if (pqEnabled) {
                    const validModes = ["iq4_nl", "q4_0", "q5_0", "q8_0"];
                    const qType = validModes.includes(pqMode) ? pqMode : "iq4_nl";
                    jsonObj.cache_type_k = qType;
                    jsonObj.cache_type_v = qType;
                } else {
                    jsonObj.cache_type_k = "f16";
                    jsonObj.cache_type_v = "f16";
                }
                if (temp !== null && !isNaN(temp)) jsonObj.temp = temp;
                if (topP !== null && !isNaN(topP)) jsonObj.top_p = topP;
                if (topK !== null && !isNaN(topK)) jsonObj.top_k = topK;
                if (minP !== null && !isNaN(minP)) jsonObj.min_p = minP;

                const newJsonStr = JSON.stringify(jsonObj, null, 2);
                if (editor.value !== newJsonStr) {
                    editor.value = newJsonStr;
                    markBatPendingChanges();
                }
                return;
            } catch (e) {
                // Incomplete JSON during typing, fall through
            }
        }

        // Batch script format fallback
        if (mmprojFile) {
            if (/set\s+["\']?MMPROJ=[^\r\n]*/i.test(content)) {
                content = content.replace(/set\s+["\']?MMPROJ=[^\r\n]*/i, `set "MMPROJ=%BASEDIR%${mmprojFile}"`);
            }
            if (/set\s+["\']?MMPROJ_FLAG=[^\r\n]*/i.test(content)) {
                content = content.replace(/set\s+["\']?MMPROJ_FLAG=[^\r\n]*/i, 'set "MMPROJ_FLAG=--mmproj "!MMPROJ!""');
            }
        } else {
            if (/set\s+["\']?MMPROJ=[^\r\n]*/i.test(content)) {
                content = content.replace(/set\s+["\']?MMPROJ=[^\r\n]*/i, 'set "MMPROJ="');
            }
            if (/set\s+["\']?MMPROJ_FLAG=[^\r\n]*/i.test(content)) {
                content = content.replace(/set\s+["\']?MMPROJ_FLAG=[^\r\n]*/i, 'set "MMPROJ_FLAG="');
            }
        }

        // Multi Token Prediction (MTP) Batch format
        if (mtpEnabled && mtpFile) {
            if (/set\s+["\']?MTP_MODEL=[^\r\n]*/i.test(content)) {
                content = content.replace(/set\s+["\']?MTP_MODEL=[^\r\n]*/i, `set "MTP_MODEL=%BASEDIR%${mtpFile}"`);
            }
            if (/--spec-draft-model\s+["\']?[^"\'\r\n]+["\']?/.test(content)) {
                if (!/--spec-draft-model\s+["\']?%MTP_MODEL%["\']?/.test(content)) {
                    content = content.replace(/--spec-draft-model\s+["\']?[^"\'\r\n]+["\']?/, `--spec-draft-model    "%BASEDIR%${mtpFile}"`);
                }
            } else {
                const mAnchor = content.match(/(!MMPROJ_FLAG!\s*\^|--model\s+["\'][^"\']+["\']\s*\^|--model\s+\S+\s*\^)/);
                if (mAnchor) {
                    content = content.replace(mAnchor[0], `${mAnchor[0]}\r\n  --spec-type           draft-mtp     ^\r\n  --spec-draft-model    "%BASEDIR%${mtpFile}" ^\r\n  --spec-draft-n-max    2             ^\r\n  --spec-draft-p-min    0.5           ^\r\n  --n-gpu-layers-draft  all           ^`);
                }
            }
            if (/--spec-type\s+[a-zA-Z0-9_\-]+/.test(content)) {
                content = content.replace(/--spec-type\s+[a-zA-Z0-9_\-]+/, '--spec-type           draft-mtp');
            }
            if (/echo\s+Modelo Borrador\s*:.*[^\r\n]*/.test(content)) {
                content = content.replace(/echo\s+Modelo Borrador\s*:.*[^\r\n]*/, `echo  Modelo Borrador : ${mtpFile} (MTP Draft)`);
            }
        } else {
            if (/set\s+["\']?MTP_MODEL=[^\r\n]*/i.test(content)) {
                content = content.replace(/set\s+["\']?MTP_MODEL=[^\r\n]*/i, 'set "MTP_MODEL="');
            }
            content = content.replace(/\r?\n\s*--spec-type\s+[^\r\n]+\s*\^/g, "");
            content = content.replace(/\r?\n\s*--spec-draft-model\s+[^\r\n]+\s*\^/g, "");
            content = content.replace(/\r?\n\s*--spec-draft-n-max\s+[^\r\n]+\s*\^/g, "");
            content = content.replace(/\r?\n\s*--spec-draft-p-min\s+[^\r\n]+\s*\^/g, "");
            content = content.replace(/\r?\n\s*--n-gpu-layers-draft\s+[^\r\n]+\s*\^/g, "");
            if (/echo\s+Modelo Borrador\s*:.*[^\r\n]*/.test(content)) {
                content = content.replace(/echo\s+Modelo Borrador\s*:.*[^\r\n]*/, 'echo  Modelo Borrador : Desactivado');
            }
        }
        if (engine) {
            const binMap = {
                "CPU": "llama-b9283-bin-win-cpu-x64",
                "VULKAN": "llama-b9297-bin-win-vulkan-x64",
                "CUDA": "llama-b9297-bin-win-cuda-x64"
            };
            const targetBin = binMap[engine];
            if (targetBin) {
                content = content.replace(/llama-(?:b\d+)?-?bin-win-(?:cuda|vulkan|cpu)-x64/g, targetBin);
            }
        }
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
            content = content.replace(/Contexto:\s*\d+\s*tokens/g, `Contexto: ${context} tokens`);
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
        if (pqEnabled) {
            flashAttn = true;
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
            const validModes = ["iq4_nl", "q4_0", "q5_0", "q8_0"];
            const qType = validModes.includes(pqMode) ? pqMode : "iq4_nl";
            const pqDescMap = {
                "iq4_nl": "Rendimiento (iq4_nl)",
                "q4_0": "Ultra Rendimiento (q4_0)",
                "q5_0": "Equilibrado (q5_0)",
                "q8_0": "Calidad (q8_0)"
            };
            const qDesc = pqDescMap[qType] || qType;

            const hasK = /--cache-type-k\s+[A-Za-z0-9_]+/.test(content);
            const hasV = /--cache-type-v\s+[A-Za-z0-9_]+/.test(content);

            if (hasK) {
                content = content.replace(/--cache-type-k\s+[A-Za-z0-9_]+/, `--cache-type-k  ${qType}`);
            }
            if (hasV) {
                content = content.replace(/--cache-type-v\s+[A-Za-z0-9_]+/, `--cache-type-v  ${qType}`);
            }
            if (!hasK && !hasV) {
                const mTarget = content.match(/(--ubatch-size\s+\d+\s*\^|--ctx-size\s+\d+\s*\^|--flash-attn\s+(?:on|off)\s*\^)/);
                if (mTarget) {
                    content = content.replace(mTarget[0], `${mTarget[0]}\r\n  --cache-type-k  ${qType}        ^\r\n  --cache-type-v  ${qType}        ^`);
                }
            } else if (hasK && !hasV) {
                content = content.replace(/(--cache-type-k\s+[A-Za-z0-9_]+\s*\^)/, `$1\r\n  --cache-type-v  ${qType}        ^`);
            } else if (hasV && !hasK) {
                content = content.replace(/(--cache-type-v\s+[A-Za-z0-9_]+\s*\^)/, `--cache-type-k  ${qType}        ^\r\n  $1`);
            }

            if (/echo\s+KV Cache\s*:[^\r\n]*\^?\|\s*Contexto:\s*\d+\s*tokens/.test(content)) {
                content = content.replace(/echo\s+KV Cache\s*:[^\r\n]*(\^?\|\s*Contexto:\s*\d+\s*tokens)/, `echo  KV Cache        : ${qDesc} $1`);
            } else if (/echo\s+KV Cache\s*:.*/.test(content)) {
                content = content.replace(/echo\s+KV Cache\s*:.*/, `echo  KV Cache        : ${qDesc}`);
            }
        } else {
            if (/--cache-type-k\s+[A-Za-z0-9_]+/.test(content)) {
                content = content.replace(/--cache-type-k\s+[A-Za-z0-9_]+/, `--cache-type-k  f16`);
            }
            if (/--cache-type-v\s+[A-Za-z0-9_]+/.test(content)) {
                content = content.replace(/--cache-type-v\s+[A-Za-z0-9_]+/, `--cache-type-v  f16`);
            }
            if (/echo\s+KV Cache\s*:[^\r\n]*\^?\|\s*Contexto:\s*\d+\s*tokens/.test(content)) {
                content = content.replace(/echo\s+KV Cache\s*:[^\r\n]*(\^?\|\s*Contexto:\s*\d+\s*tokens)/, `echo  KV Cache        : FP16 (sin comprimir) $1`);
            } else if (/echo\s+KV Cache\s*:.*/.test(content)) {
                content = content.replace(/echo\s+KV Cache\s*:.*/, `echo  KV Cache        : FP16 (sin comprimir)`);
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
    } catch (e) {
        console.error("Error in syncUItoBatEditor:", e);
    } finally {
        isSyncing = false;
    }
}

/**
 * Synchronizes modifications typed directly into the raw .BAT or .JSON textarea back into the UI controls.
 */
function syncBatEditorToUI() {
    if (isSyncing) return;
    const editor = document.getElementById("editor-bat-content");
    if (!editor) return;

    const content = editor.value;
    if (!content) return;

    // JSON format synchronization
    if (content.trim().startsWith("{")) {
        try {
            const data = JSON.parse(content);
            isSyncing = true;
            try {
                if (data.port && document.getElementById("input-port")) {
                    document.getElementById("input-port").value = data.port;
                }
                if (data.context && document.getElementById("input-context")) {
                    document.getElementById("input-context").value = data.context;
                }
                if (data.threads && document.getElementById("input-threads")) {
                    document.getElementById("input-threads").value = data.threads;
                }
                if (data.engine && document.getElementById("select-engine")) {
                    document.getElementById("select-engine").value = data.engine;
                    handleEngineUI(data.engine);
                }
                if (data.ngl !== undefined && document.getElementById("input-ngl")) {
                    document.getElementById("input-ngl").value = data.ngl;
                }
                if (data.flash_attn !== undefined && document.getElementById("check-flash-attn")) {
                    document.getElementById("check-flash-attn").checked = !!data.flash_attn;
                }
                const checkPq = document.getElementById("check-pq-enable");
                const selectPq = document.getElementById("select-pq-mode");
                const modeGroup = document.getElementById("pq-mode-group");
                if (data.cache_type_k && checkPq && selectPq) {
                    const ck = data.cache_type_k.toLowerCase();
                    if (ck !== "f16" && ck !== "none") {
                        checkPq.checked = true;
                        if (modeGroup) modeGroup.style.display = "flex";
                        if (ck.includes("iq4_nl")) selectPq.value = "iq4_nl";
                        else if (ck.includes("q4_0")) selectPq.value = "q4_0";
                        else if (ck.includes("q5_0")) selectPq.value = "q5_0";
                        else if (ck.includes("q8_0")) selectPq.value = "q8_0";
                        else selectPq.value = "iq4_nl";
                    } else {
                        checkPq.checked = false;
                        if (modeGroup) modeGroup.style.display = "none";
                    }
                }
                if (data.temp !== undefined && document.getElementById("input-temp")) {
                    document.getElementById("input-temp").value = data.temp;
                }
                if (data.top_p !== undefined && document.getElementById("input-topp")) {
                    document.getElementById("input-topp").value = data.top_p;
                }
                if (data.top_k !== undefined && document.getElementById("input-topk")) {
                    document.getElementById("input-topk").value = data.top_k;
                }
                if (data.min_p !== undefined && document.getElementById("input-minp")) {
                    document.getElementById("input-minp").value = data.min_p;
                }
                const checkVision = document.getElementById("check-vision");
                const lblVision = document.getElementById("lbl-vision-file");
                if (checkVision && data.mmproj_file !== undefined) {
                    const isVisionActive = !!(data.mmproj_file && data.mmproj_file.trim() !== "");
                    checkVision.checked = isVisionActive;
                    const dispFile = data.mmproj_file || checkVision.dataset.availableFile || "";
                    if (lblVision) {
                        if (isVisionActive) {
                            lblVision.innerText = `(${dispFile})`;
                            lblVision.style.color = "var(--accent-emerald)";
                        } else {
                            lblVision.innerText = dispFile ? `(${dispFile} — Desactivado)` : "(Desactivado)";
                            lblVision.style.color = "var(--text-muted)";
                        }
                    }
                }
                const checkMtp = document.getElementById("check-mtp");
                const lblMtp = document.getElementById("lbl-mtp-file");
                if (checkMtp && data.spec_draft_model !== undefined) {
                    const isMtpActive = !!(data.spec_draft_model && data.spec_draft_model.trim() !== "" && data.spec_type);
                    checkMtp.checked = isMtpActive;
                    const dispMtp = data.spec_draft_model || checkMtp.dataset.availableFile || "";
                    if (lblMtp) {
                        if (isMtpActive) {
                            lblMtp.innerText = `(${dispMtp})`;
                            lblMtp.style.color = "var(--accent-emerald)";
                        } else {
                            lblMtp.innerText = dispMtp ? `(${dispMtp} — Desactivado)` : "(Desactivado)";
                            lblMtp.style.color = "var(--text-muted)";
                        }
                    }
                }
                markBatPendingChanges();
                return;
            } finally {
                isSyncing = false;
            }
        } catch (e) {
            // User still typing JSON, ignore syntax errors temporarily
        }
    }

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
                if (ck.includes("iq4_nl")) selectPq.value = "iq4_nl";
                else if (ck.includes("q4_0")) selectPq.value = "q4_0";
                else if (ck.includes("q5_0")) selectPq.value = "q5_0";
                else if (ck.includes("q8_0")) selectPq.value = "q8_0";
                else selectPq.value = "iq4_nl";
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
        const mMm = content.match(/set\s+["\']?MMPROJ=(?:%BASEDIR%)?([^"\'\r\n]+)/i);
        const checkVision = document.getElementById("check-vision");
        const lblVision = document.getElementById("lbl-vision-file");
        if (checkVision) {
            if (mMm && mMm[1].trim() !== "") {
                const fName = mMm[1].trim();
                checkVision.checked = true;
                checkVision.dataset.availableFile = fName;
                if (lblVision) {
                    lblVision.innerText = `(${fName})`;
                    lblVision.style.color = "var(--accent-emerald)";
                }
            } else {
                checkVision.checked = false;
                if (lblVision && checkVision.dataset.availableFile) {
                    lblVision.innerText = `(${checkVision.dataset.availableFile} — Desactivado)`;
                    lblVision.style.color = "var(--text-muted)";
                }
            }
        }
        const mMtp = content.match(/--spec-draft-model\s+["\']?([^"\'\r\n]+)["\']?/i) || content.match(/set\s+["\']?MTP_MODEL=(?:%BASEDIR%)?([^"\'\r\n]+)/i);
        const hasSpecType = /--spec-type\s+([a-zA-Z0-9_\-]+)/i.test(content);
        const checkMtp = document.getElementById("check-mtp");
        const lblMtp = document.getElementById("lbl-mtp-file");
        if (checkMtp) {
            if (mMtp && hasSpecType && mMtp[1].trim() !== "") {
                const fName = mMtp[1].trim().replace("%BASEDIR%", "");
                checkMtp.checked = true;
                checkMtp.dataset.availableFile = fName;
                if (lblMtp) {
                    lblMtp.innerText = `(${fName})`;
                    lblMtp.style.color = "var(--accent-emerald)";
                }
            } else {
                checkMtp.checked = false;
                if (lblMtp && checkMtp.dataset.availableFile) {
                    lblMtp.innerText = `(${checkMtp.dataset.availableFile} — Desactivado)`;
                    lblMtp.style.color = "var(--text-muted)";
                }
            }
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
                const ext = (currentBatchDetails.filename && currentBatchDetails.filename.endsWith(".json")) ? ".json" : ".bat";
                backupPill.innerText = `Backup: ${ext}.bak existe`;
                backupPill.style.color = "var(--accent-emerald)";
            }

            if (saveResult) {
                saveResult.innerText = "✅ Guardado (.json y .bat sincronizados)";
                saveResult.style.color = "var(--accent-emerald)";
            }
            appendLogLine(`[SUCCESS] Configuración ${currentBatchDetails.filename} guardada (.json y .bat sincronizados).`);
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

    handleEngineUI(engine);

    if (currentBatchDetails) {
        // In Batch Runner mode, preserve model-calibrated context/ngl (or 0 for CPU), sync KV cache compression
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
    const selectPq = document.getElementById("select-pq-mode");
    const checkFa = document.getElementById("check-flash-attn");
    if (enabled) {
        modeGroup.style.display = "flex";
        if (selectPq && !selectPq.value) {
            selectPq.value = "iq4_nl";
        }
        // llama.cpp strictly requires flash_attn on when V cache is quantized
        if (checkFa) {
            checkFa.checked = true;
        }
    } else {
        modeGroup.style.display = "none";
    }
    onEngineOrPqChange();
}

function onFlashAttnCheckboxChange() {
    const checkFa = document.getElementById("check-flash-attn");
    const checkPq = document.getElementById("check-pq-enable");
    const modeGroup = document.getElementById("pq-mode-group");
    if (checkFa && !checkFa.checked && checkPq && checkPq.checked) {
        // Disabling Flash Attention is incompatible with quantized V cache in llama.cpp
        checkPq.checked = false;
        if (modeGroup) modeGroup.style.display = "none";
    }
    syncUItoBatEditor();
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
            try {
                syncUItoBatEditor();
            } catch (err) {
                console.error("Error in syncUItoBatEditor before launch:", err);
            }

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
            const launchPath = currentBatchDetails.bat_path || (currentBatchDetails.path && currentBatchDetails.path.endsWith(".json") ? currentBatchDetails.path.replace(/\.json$/i, ".bat") : currentBatchDetails.path);

            appendLogLine(`[SYSTEM] Lanzando servidor: ${currentBatchDetails.filename} (${modelLabel}) en puerto ${port}...`);
            setButtonState("loading");

            try {
                const res = await api.launch_batch_script(launchPath, port);
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
        "check-flash-attn", "check-pq-enable", "select-pq-mode",
        "input-temp", "input-topp", "input-topk", "input-minp"
    ];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", syncUItoBatEditor);
            el.addEventListener("change", syncUItoBatEditor);
        }
    });

    const engineEl = document.getElementById("select-engine");
    if (engineEl) {
        engineEl.addEventListener("change", onEngineOrPqChange);
    }

    const visionEl = document.getElementById("check-vision");
    if (visionEl) {
        visionEl.addEventListener("change", onVisionCheckboxChange);
    }

    const mtpEl = document.getElementById("check-mtp");
    if (mtpEl) {
        mtpEl.addEventListener("change", onMtpCheckboxChange);
    }

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

// ==========================================
// LLAMA.CPP UPDATE CHECKER & INSTALLER
// ==========================================
let currentLlamaUpdateData = null;

async function checkLlamaUpdates() {
    if (!api) return;
    const btn = document.getElementById("btn-check-llama-updates");
    const spinner = document.getElementById("spinner-update-llama");
    const engineSel = document.getElementById("select-engine");
    const engine = engineSel ? engineSel.value : "CUDA";

    if (btn) btn.disabled = true;
    if (spinner) spinner.style.display = "inline";

    try {
        const res = await api.check_llama_updates(engine);
        if (!res || !res.success) {
            alert(res && res.message ? res.message : "Error desconocido al buscar actualizaciones.");
            return;
        }

        if (!res.has_update) {
            alert(`¡Estás al día!\nYa cuentas con la versión más reciente instalada (${res.current_version}).`);
            return;
        }

        currentLlamaUpdateData = res;

        // Populate and show modal
        const modal = document.getElementById("modal-llama-update");
        const lblCurrent = document.getElementById("lbl-update-current");
        const lblLatest = document.getElementById("lbl-update-latest");
        const lblAsset = document.getElementById("lbl-update-asset");
        const lblNotes = document.getElementById("lbl-update-notes");
        const linkGh = document.getElementById("btn-update-github-link");
        const progContainer = document.getElementById("update-progress-container");
        const btnInstall = document.getElementById("btn-start-update-install");

        if (lblCurrent) lblCurrent.innerText = res.current_version;
        if (lblLatest) lblLatest.innerText = res.latest_version;
        if (lblAsset) lblAsset.innerText = res.asset_name ? `${res.asset_name} (${res.size_mb} MB)` : "Sin binario directo disponible";
        if (lblNotes) lblNotes.innerText = res.release_notes || "Sin notas de versión disponibles.";
        if (linkGh && res.html_url) linkGh.href = res.html_url;

        if (progContainer) progContainer.style.display = "none";
        if (btnInstall) {
            btnInstall.disabled = !res.download_url;
            btnInstall.innerText = "⬇️ Descargar e Instalar";
            btnInstall.className = "btn-primary start";
        }

        if (modal) modal.classList.add("active");
    } catch (err) {
        console.error("Error al buscar actualizaciones de llama.cpp:", err);
        alert("Fallo de red o error al conectar con GitHub.");
    } finally {
        if (btn) btn.disabled = false;
        if (spinner) spinner.style.display = "none";
    }
}

function closeLlamaUpdateModal() {
    const modal = document.getElementById("modal-llama-update");
    if (modal) modal.classList.remove("active");
}

async function startLlamaUpdateDownload() {
    if (!api || !currentLlamaUpdateData || !currentLlamaUpdateData.download_url) return;
    const btnInstall = document.getElementById("btn-start-update-install");
    const progContainer = document.getElementById("update-progress-container");

    if (btnInstall) {
        btnInstall.disabled = true;
        btnInstall.innerText = "⏳ Descargando...";
    }
    if (progContainer) {
        progContainer.style.display = "flex";
    }

    try {
        const res = await api.download_and_install_llama_update(
            currentLlamaUpdateData.download_url,
            currentLlamaUpdateData.asset_name,
            currentLlamaUpdateData.engine
        );
        if (!res || !res.success) {
            alert(res && res.message ? res.message : "Error al iniciar descarga de actualización.");
            if (btnInstall) {
                btnInstall.disabled = false;
                btnInstall.innerText = "⬇️ Descargar e Instalar";
            }
        }
    } catch (err) {
        console.error("Error al iniciar descarga de actualización:", err);
        alert("Fallo de comunicación con el motor de escritorio.");
        if (btnInstall) {
            btnInstall.disabled = false;
            btnInstall.innerText = "⬇️ Descargar e Instalar";
        }
    }
}

window.updateLlamaUpdateProgress = function(percent, speed, downloaded_mb, total_mb, status, message) {
    const bar = document.getElementById("bar-update-progress");
    const lblPct = document.getElementById("lbl-update-pct");
    const lblMetrics = document.getElementById("lbl-update-metrics");
    const lblSpeed = document.getElementById("lbl-update-speed");
    const lblStatus = document.getElementById("lbl-update-status");
    const btnInstall = document.getElementById("btn-start-update-install");

    if (bar) bar.style.width = `${percent}%`;
    if (lblPct) lblPct.innerText = `${percent.toFixed(1)}%`;
    if (lblMetrics) lblMetrics.innerText = `${downloaded_mb.toFixed(1)} / ${total_mb.toFixed(1)} MB`;
    if (lblSpeed) lblSpeed.innerText = `${speed.toFixed(2)} MB/s`;

    if (status === "downloading") {
        if (lblStatus) lblStatus.innerText = message || "Descargando binarios desde GitHub...";
    } else if (status === "extracting") {
        if (lblStatus) lblStatus.innerText = message || "Extrayendo y verificando librerías CUDA...";
        if (bar) bar.style.width = "100%";
    } else if (status === "completed") {
        if (lblStatus) {
            lblStatus.innerText = message || "¡Actualización instalada con éxito!";
            lblStatus.style.color = "var(--accent-emerald)";
        }
        if (bar) {
            bar.style.width = "100%";
            bar.style.background = "var(--accent-emerald)";
        }
        if (btnInstall) {
            btnInstall.innerText = "✅ ¡Actualizado!";
            btnInstall.disabled = true;
        }
        // Refresh hardware engines and batch model details
        if (typeof onEngineOrPqChange === "function") {
            setTimeout(() => {
                onEngineOrPqChange();
            }, 1000);
        }
    } else if (status === "error") {
        if (lblStatus) {
            lblStatus.innerText = message || "Error en la actualización.";
            lblStatus.style.color = "var(--accent-rose)";
        }
        if (btnInstall) {
            btnInstall.disabled = false;
            btnInstall.innerText = "Reintentar Descarga";
        }
    }
};

