// downloader.js - Download Library and Model Management

function initLocalModelsTableSorting() {
    const headers = document.querySelectorAll(".models-table th.sortable");
    if (!headers.length) return;
    updateLocalModelsSortUI();
}

function sortLocalModelsBy(key) {
    if (!key) return;
    if (localModelsSort.key === key) {
        localModelsSort.direction = localModelsSort.direction === "asc" ? "desc" : "asc";
    } else {
        localModelsSort.key = key;
        localModelsSort.direction = "asc";
    }
    updateLocalModelsSortUI();
    renderLocalModelsLibrary();
}

function updateLocalModelsSortUI() {
    const headers = document.querySelectorAll(".models-table th.sortable");
    headers.forEach((th) => {
        th.classList.remove("sort-asc", "sort-desc");
        if (th.dataset.sortKey === localModelsSort.key) {
            th.classList.add(localModelsSort.direction === "asc" ? "sort-asc" : "sort-desc");
        }
    });
}

function getSortableModelsList() {
    const rows = [];
    for (const [category, list] of Object.entries(scannedModelsMap || {})) {
        if (!list || !list.length) continue;
        list.forEach((model) => rows.push({ category, model }));
    }

    const dir = localModelsSort.direction === "asc" ? 1 : -1;
    rows.sort((a, b) => compareModels(a, b, localModelsSort.key) * dir);
    return rows;
}

function compareModels(a, b, key) {
    if (key === "size_gb") {
        return safeNumberCompare(parseFloat(a.model.size_gb), parseFloat(b.model.size_gb));
    }
    if (key === "download_date" || key === "last_used") {
        return safeNumberCompare(Date.parse(a.model[key]), Date.parse(b.model[key]));
    }

    const aVal = modelStringValue(a, key);
    const bVal = modelStringValue(b, key);
    return aVal.localeCompare(bVal, undefined, { numeric: true, sensitivity: "base" });
}

function safeNumberCompare(aVal, bVal) {
    const aInvalid = Number.isNaN(aVal);
    const bInvalid = Number.isNaN(bVal);
    if (aInvalid && bInvalid) return 0;
    if (aInvalid) return 1;
    if (bInvalid) return -1;
    return aVal - bVal;
}

function modelStringValue(entry, key) {
    if (key === "name") return entry.model.filename || "";
    if (key === "category") return entry.category || "";
    if (key === "parameters") return entry.model.parameters || "";
    return `${entry.model[key] || ""}`;
}

// Dynamic Asynchronous Progress Stream (Proactive PUSH from Python)
window.updateDownloadProgress = function(percent, speed, downloaded_mb, total_mb, status, error_msg, category, filename) {
    const card = document.getElementById("active-download-card");
    
    if (filename) {
        activeDownloadName = filename;
    }
    if (category) {
        activeDownloadCategory = category;
    }
    
    if (status === "downloading") {
        card.style.display = "block";
        document.getElementById("lbl-downloading-name").innerText = `Downloading ${activeDownloadName}...`;
        document.getElementById("lbl-download-speed").innerText = speed.toFixed(2);
        document.getElementById("lbl-download-bytes").innerText = `${downloaded_mb.toFixed(1)}/${total_mb.toFixed(1)} MB`;
        document.getElementById("download-progress-bar").style.width = `${percent}%`;
        document.getElementById("lbl-download-percent").innerText = `${percent.toFixed(1)}%`;
        
        // Calculate elapsed time locally
        if (downloadStartTime) {
            const elapsed = Math.round((Date.now() - downloadStartTime) / 1000);
            document.getElementById("lbl-download-time").innerText = elapsed;
        }
    } else if (status === "completed") {
        card.style.display = "none";
        appendLogLine(`[SUCCESS] Download completed and integrated: ${activeDownloadName}`);
        alert(`Model downloaded successfully: ${activeDownloadName}`);
        
        // Reset state
        activeDownloadName = "";
        activeDownloadCategory = "";
        downloadStartTime = null;
        
        // Reload local GGUFs
        if (typeof reloadModelDropdown === 'function') reloadModelDropdown();
    } else if (status === "cancelled") {
        card.style.display = "none";
        appendLogLine(`[WARNING] Download cancelled by user: ${activeDownloadName}`, "error");
        alert(`Download cancelled: ${activeDownloadName}`);
        
        activeDownloadName = "";
        activeDownloadCategory = "";
        downloadStartTime = null;
    } else if (status === "error") {
        card.style.display = "none";
        appendLogLine(`[ERROR] Download failed: ${error_msg}`, "error");
        alert(`Download failed: ${error_msg}`);
        
        activeDownloadName = "";
        activeDownloadCategory = "";
        downloadStartTime = null;
    }
}

async function cancelActiveDownload() {
    if (!api) return;
    if (!activeDownloadName) return;
    
    const confirmCancel = confirm(`Are you sure you want to cancel downloading ${activeDownloadName}?`);
    if (!confirmCancel) return;
    
    try {
        appendLogLine(`[SYSTEM] Requesting download cancellation for: ${activeDownloadName}...`);
        const res = await api.cancelar_descarga(activeDownloadName, activeDownloadCategory);
        appendLogLine(`[SYSTEM] ${res.message}`);
    } catch (e) {
        console.error("Failed to cancel download", e);
    }
}

// Downloaded Local Models Library Manager
function renderLocalModelsLibrary() {
    const tbody = document.getElementById("local-models-tbody");
    const container = document.getElementById("local-models-table-container");
    if (!tbody || !container) return;
    
    tbody.innerHTML = "";
    let hasLocalModels = false;
    
    const rows = getSortableModelsList();
    rows.forEach(({ category, model }) => {
        hasLocalModels = true;
        const tr = document.createElement("tr");

        // Fallbacks if data is missing from older backend versions
        const params = model.parameters || "Unknown";
        const sizeGB = model.size_gb !== undefined ? `${model.size_gb} GB` : (model.size || "Unknown");
        const dlDate = model.download_date || "Unknown";
        const lastUsed = model.last_used || "Never";

        tr.innerHTML = `
            <td class="model-name">${model.filename}</td>
            <td><span class="badge ${category}">${category}</span></td>
            <td><span class="param-badge">${params}</span></td>
            <td style="font-weight: 500;">${sizeGB}</td>
            <td class="date-cell">${dlDate}</td>
            <td class="date-cell">${lastUsed}</td>
            <td>
                <button class="btn-secondary" onclick="deleteLocalModel('${category}', '${model.filename}')" style="background-color: rgba(244, 63, 94, 0.12); border-color: rgba(244, 63, 94, 0.3); color: var(--accent-rose); font-size: 11px; padding: 4px 10px; font-weight:600; cursor:pointer;">🗑️ Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    if (!hasLocalModels) {
        container.style.display = "none";
        // Create an empty state message if not exists
        let emptyState = document.getElementById("local-models-empty-state");
        if (!emptyState) {
            emptyState = document.createElement("div");
            emptyState.id = "local-models-empty-state";
            emptyState.className = "subtitle";
            emptyState.style.textAlign = "center";
            emptyState.style.padding = "20px";
            emptyState.innerText = "You have no GGUF models downloaded. Use the HF Search or Custom Download options below to pull some models!";
            container.parentNode.insertBefore(emptyState, container.nextSibling);
        }
        emptyState.style.display = "block";
    } else {
        container.style.display = "block";
        const emptyState = document.getElementById("local-models-empty-state");
        if (emptyState) emptyState.style.display = "none";
    }
}

async function deleteLocalModel(category, filename) {
    if (!api) return;
    
    const confirmDelete = confirm(`Are you sure you want to permanently delete this model file?\n\nFile: ${filename}\nCategory: ${category.toUpperCase()}\n\nThis action cannot be undone.`);
    if (!confirmDelete) return;
    
    try {
        appendLogLine(`[SYSTEM] Requesting permanent deletion of model: ${filename}...`);
        const res = await api.delete_local_model(category, filename);
        if (res.success) {
            appendLogLine(`[SUCCESS] ${res.message}`);
            alert(res.message);
            if (typeof reloadModelDropdown === 'function') await reloadModelDropdown();
        } else {
            alert(res.message);
            appendLogLine(`[ERROR] Deletion failed: ${res.message}`, "error");
        }
    } catch (e) {
        alert("Failed to delete model: " + e);
        appendLogLine(`[ERROR] Delete exception: ${e}`, "error");
    }
}

function onUnifiedInput() {
    const input = document.getElementById("input-unified-search").value.trim();
    const btn = document.getElementById("btn-unified-action");
    const catSelect = document.getElementById("select-custom-cat");
    
    if (input.startsWith("http://") || input.startsWith("https://")) {
        btn.innerText = "📥 Download";
        catSelect.style.display = "block";
    } else {
        btn.innerText = "🔍 Search Hub";
        catSelect.style.display = "none";
    }
}

async function handleUnifiedAction() {
    const input = document.getElementById("input-unified-search").value.trim();
    if (!input) {
        alert("Please enter a keyword to search or a direct download URL.");
        return;
    }
    
    if (input.startsWith("http://") || input.startsWith("https://")) {
        // Direct Download
        if (!api) return;
        const category = document.getElementById("select-custom-cat").value;
        const filename = input.split("/").pop().split("?")[0] || "custom_model.gguf";
        
        try {
            downloadStartTime = Date.now();
            const res = await api.start_download("CUSTOM", input, filename, category);
            if (res.success) {
                appendLogLine(`[SYSTEM] ${res.message}`);
                document.getElementById("input-unified-search").value = "";
                onUnifiedInput(); // reset state
            } else {
                alert(res.message);
            }
        } catch (e) {
            alert("Connection error: " + e);
        }
    } else {
        // Search
        triggerHfSearch(input);
    }
}

// ==========================================
// Hugging Face Hub Live Search Logic
// ==========================================

async function triggerHfSearch(query) {
    if (!api) return;
    
    if (!query) {
        alert("Please enter a keyword to search (e.g. llama, phi, qwen).");
        return;
    }
    
    const btn = document.getElementById("btn-unified-action");
    const oldText = btn.innerText;
    btn.innerText = "⏳ Searching...";
    btn.disabled = true;
    
    try {
        appendLogLine(`[SYSTEM] Searching Hugging Face Hub for GGUF models matching: "${query}"...`);
        const res = await api.search_hf_models(query);
        
        if (res.success) {
            const resultsContainer = document.getElementById("hf-search-results");
            const resultsSection = document.getElementById("search-results-section");
            resultsContainer.innerHTML = "";
            
            if (res.results.length === 0) {
                resultsContainer.innerHTML = `<p class="subtitle" style="grid-column: 1/-1; text-align: center; padding: 20px;">No GGUF models found matching "${query}". Try different keywords.</p>`;
            } else {
                res.results.forEach(item => {
                    const card = document.createElement("div");
                    card.className = "model-search-card";
                    
                    const safeId = item.id.replace(/\//g, '-');
                    
                    card.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                            <h3 title="${item.id}">${item.id}</h3>
                        </div>
                        <p class="subtitle" style="font-family: var(--font-mono); font-size: 11px;">
                            📥 ${item.downloads.toLocaleString()} downloads  •  ❤️ ${item.likes.toLocaleString()} likes
                        </p>
                        <div style="margin-top: auto; display: flex; flex-direction: column; gap: 10px;">
                            <button class="btn-secondary" id="btn-explore-${safeId}" onclick="exploreQuantizations('${item.id}')" style="width: 100%; height: 38px;">
                                🔍 Explore GGUF Files
                            </button>
                            <div class="quant-explorer-section" id="quant-explorer-${safeId}" style="display: none;">
                                <!-- Will be loaded dynamically -->
                            </div>
                        </div>
                    `;
                    resultsContainer.appendChild(card);
                });
            }
            resultsSection.style.display = "block";
            appendLogLine(`[SUCCESS] Found ${res.results.length} Hugging Face repositories matching your search.`);
        } else {
            alert(res.message);
            appendLogLine(`[ERROR] Hugging Face Hub search failed: ${res.message}`, "error");
        }
    } catch (e) {
        alert("Search error: " + e);
        appendLogLine(`[ERROR] Search exception: ${e}`, "error");
    } finally {
        btn.innerText = oldText;
        btn.disabled = false;
    }
}

function clearSearchResults() {
    document.getElementById("search-results-section").style.display = "none";
    document.getElementById("hf-search-results").innerHTML = "";
    document.getElementById("input-unified-search").value = "";
    onUnifiedInput(); // reset the button
    appendLogLine("[SYSTEM] Search results cleared.");
}

async function exploreQuantizations(modelId) {
    if (!api) return;
    
    const safeId = modelId.replace(/\//g, '-');
    const btn = document.getElementById(`btn-explore-${safeId}`);
    const explorer = document.getElementById(`quant-explorer-${safeId}`);
    
    // Toggle if already loaded and shown
    if (explorer.style.display === "flex") {
        explorer.style.display = "none";
        btn.innerText = "🔍 Explore GGUF Files";
        return;
    }
    
    const oldText = btn.innerText;
    btn.innerText = "⏳ Scanning files...";
    btn.disabled = true;
    
    try {
        appendLogLine(`[SYSTEM] Querying file tree for repository: ${modelId}...`);
        const res = await api.get_hf_model_files(modelId);
        
        if (res.success) {
            if (res.files.length === 0) {
                explorer.innerHTML = `<p class="subtitle" style="font-size: 11px; text-align: center; color: var(--accent-rose);">No .gguf files found in this repository's main branch.</p>`;
                explorer.style.display = "flex";
            } else {
                let optionsHtml = res.files.map(f => `<option value="${f}">${f}</option>`).join("");
                
                explorer.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label for="select-quant-${safeId}">Available Quantizations</label>
                        <select id="select-quant-${safeId}" class="quant-select">
                            ${optionsHtml}
                        </select>
                    </div>
                    <div class="quant-actions">
                        <select id="select-cat-${safeId}">
                            <option value="edge">EDGE</option>
                            <option value="large" selected>LARGE</option>
                            <option value="coder">CODER</option>
                        </select>
                        <button class="btn-primary" onclick="downloadSelectedQuant('${modelId}')">Download</button>
                    </div>
                `;
                explorer.style.display = "flex";
                appendLogLine(`[SYSTEM] Loaded ${res.files.length} GGUF files from ${modelId}. Choose a quantization level and local category.`);
            }
            btn.innerText = "Close Explorer 📂";
        } else {
            alert(res.message);
            appendLogLine(`[ERROR] Failed to explore GGUF files: ${res.message}`, "error");
        }
    } catch (e) {
        alert("Failed to scan repository files: " + e);
    } finally {
        btn.disabled = false;
        if (btn.innerText === "⏳ Scanning files...") {
            btn.innerText = oldText;
        }
    }
}

async function downloadSelectedQuant(modelId) {
    if (!api) return;
    
    const safeId = modelId.replace(/\//g, '-');
    const selectFile = document.getElementById(`select-quant-${safeId}`);
    const selectCat = document.getElementById(`select-cat-${safeId}`);
    
    if (!selectFile) return;
    const filename = selectFile.value;
    const category = selectCat.value;
    
    const url = `https://huggingface.co/${modelId}/resolve/main/${filename}`;
    
    const confirmDl = confirm(`Do you want to download this quantization from Hugging Face?\n\nFile: ${filename}\nCategory: ${category.toUpperCase()}\n\nThis will run in a background thread and does not block the UI.`);
    if (!confirmDl) return;
    
    try {
        downloadStartTime = Date.now();
        appendLogLine(`[SYSTEM] Starting download of ${filename} to category ${category}...`);
        const res = await api.start_download("CUSTOM", url, filename, category);
        if (res.success) {
            appendLogLine(`[SYSTEM] ${res.message}`);
            switchTab("download");
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            alert(res.message);
        }
    } catch (e) {
        alert("Connection error: " + e);
    }
}
