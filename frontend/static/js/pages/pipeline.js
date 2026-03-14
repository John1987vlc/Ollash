/**
 * Pipeline Builder — drag-and-drop pipeline composition + SSE execution.
 *
 * State:
 *   allPhases     : array of phase metadata from /api/pipelines/phases
 *   pipelines     : array of saved pipelines
 *   currentPipeline : pipeline object currently loaded in the builder (null if new)
 *   sequence      : ordered array of phase_id strings currently in the builder
 *   activeSSE     : EventSource for live run streaming (null if idle)
 */

"use strict";

const PipelineApp = (() => {
  // ── State ──────────────────────────────────────────────────────────────
  let allPhases = [];
  let pipelines = [];
  let currentPipeline = null;
  let sequence = [];
  let activeSSE = null;
  let dragSrcIndex = null;

  // ── DOM refs ────────────────────────────────────────────────────────────
  const el = (id) => document.getElementById(id);

  // ── Init ────────────────────────────────────────────────────────────────
  async function init() {
    await Promise.all([loadPhases(), loadPipelines()]);
    bindButtons();
    renderPalette();
    renderPipelineList();
    renderSequence();
  }

  // ── API helpers ─────────────────────────────────────────────────────────
  function authHeaders() {
    const token = localStorage.getItem("ollash_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function apiFetch(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...authHeaders() },
      ...options,
    });
    if (!res.ok) {
      const msg = await res.text().catch(() => res.statusText);
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  async function loadPhases() {
    allPhases = await apiFetch("/api/pipelines/phases");
  }

  async function loadPipelines() {
    try {
      pipelines = await apiFetch("/api/pipelines");
    } catch {
      pipelines = [];
    }
  }

  // ── Palette ─────────────────────────────────────────────────────────────
  function renderPalette(filter = "") {
    const container = el("palette-categories");
    if (!container) return;

    const lower = filter.toLowerCase();
    const categories = [...new Set(allPhases.map((p) => p.category))];
    container.innerHTML = "";

    for (const cat of categories) {
      const phases = allPhases.filter(
        (p) =>
          p.category === cat &&
          (!lower || p.label.toLowerCase().includes(lower) || p.description.toLowerCase().includes(lower))
      );
      if (!phases.length) continue;

      const catEl = document.createElement("div");
      catEl.className = "palette-category";
      catEl.innerHTML = `<div class="palette-cat-title">${cat}</div>`;

      for (const phase of phases) {
        const inSeq = sequence.includes(phase.id);
        const item = document.createElement("div");
        item.className = "palette-phase-item" + (inSeq ? " in-pipeline" : "");
        item.draggable = !inSeq;
        item.dataset.phaseId = phase.id;
        item.innerHTML = `
          <div class="pal-label">${phase.label}</div>
          <div class="pal-desc" title="${phase.description}">${phase.description}</div>
        `;
        if (!inSeq) {
          item.addEventListener("dragstart", onPaletteDragStart);
        }
        // Double-click adds to sequence
        item.addEventListener("dblclick", () => {
          if (!inSeq) addPhaseToSequence(phase.id);
        });
        catEl.appendChild(item);
      }

      container.appendChild(catEl);
    }
  }

  // ── Sequence / Builder canvas ────────────────────────────────────────────
  function renderSequence() {
    const seqEl = el("phase-sequence");
    const hint = el("drop-hint");
    if (!seqEl) return;

    seqEl.innerHTML = "";
    if (hint) hint.style.display = sequence.length ? "none" : "block";

    for (let i = 0; i < sequence.length; i++) {
      const phaseId = sequence[i];
      const meta = allPhases.find((p) => p.id === phaseId) || { id: phaseId, label: phaseId, category: "" };
      const card = document.createElement("div");
      card.className = "phase-card";
      card.draggable = true;
      card.dataset.index = i;
      card.innerHTML = `
        <div class="phase-index">${i + 1}</div>
        <div class="phase-info">
          <div class="phase-card-label">${meta.label}</div>
          <div class="phase-card-cat">${meta.category}</div>
        </div>
        <button class="remove-phase-btn" title="Remove" data-index="${i}">✕</button>
      `;
      card.addEventListener("dragstart", onCardDragStart);
      card.addEventListener("dragover", onCardDragOver);
      card.addEventListener("dragleave", onCardDragLeave);
      card.addEventListener("drop", onCardDrop);
      card.addEventListener("dragend", onCardDragEnd);
      card.querySelector(".remove-phase-btn").addEventListener("click", (e) => {
        const idx = parseInt(e.currentTarget.dataset.index, 10);
        removePhaseAt(idx);
      });
      seqEl.appendChild(card);
    }

    // Drop zone at bottom of sequence
    const dropZone = document.createElement("div");
    dropZone.className = "phase-drop-zone";
    dropZone.dataset.index = sequence.length;
    dropZone.style.cssText = "height:40px;border:2px dashed var(--border-color);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--text-secondary);font-size:0.75rem;";
    dropZone.textContent = "Drop phase here";
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.style.borderColor = "var(--accent-primary)"; });
    dropZone.addEventListener("dragleave", () => { dropZone.style.borderColor = "var(--border-color)"; });
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--border-color)";
      handleDrop(sequence.length, e.dataTransfer.getData("text/plain"));
    });
    seqEl.appendChild(dropZone);

    // Update button state
    const saveBtn = el("save-pipeline-btn");
    const runBtn = el("run-pipeline-btn");
    if (saveBtn) saveBtn.disabled = sequence.length === 0;
    if (runBtn) runBtn.disabled = sequence.length === 0;
  }

  function addPhaseToSequence(phaseId) {
    if (!sequence.includes(phaseId)) {
      sequence.push(phaseId);
      renderSequence();
      renderPalette(el("palette-search")?.value || "");
      markDirty();
    }
  }

  function removePhaseAt(index) {
    sequence.splice(index, 1);
    renderSequence();
    renderPalette(el("palette-search")?.value || "");
    markDirty();
  }

  function markDirty() {
    const saveBtn = el("save-pipeline-btn");
    if (saveBtn) saveBtn.classList.add("btn-pulse");
  }

  // ── Drag-and-drop from palette ───────────────────────────────────────────
  function onPaletteDragStart(e) {
    e.dataTransfer.setData("text/plain", e.currentTarget.dataset.phaseId);
    e.dataTransfer.effectAllowed = "copy";
  }

  // ── Drag-and-drop reorder inside sequence ────────────────────────────────
  function onCardDragStart(e) {
    dragSrcIndex = parseInt(e.currentTarget.dataset.index, 10);
    e.dataTransfer.setData("text/plain", sequence[dragSrcIndex]);
    e.dataTransfer.effectAllowed = "move";
    e.currentTarget.classList.add("dragging");
  }

  function onCardDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    e.currentTarget.classList.add("drag-over");
  }

  function onCardDragLeave(e) {
    e.currentTarget.classList.remove("drag-over");
  }

  function onCardDrop(e) {
    e.preventDefault();
    const targetIndex = parseInt(e.currentTarget.dataset.index, 10);
    const phaseId = e.dataTransfer.getData("text/plain");
    e.currentTarget.classList.remove("drag-over");
    handleDrop(targetIndex, phaseId);
  }

  function onCardDragEnd(e) {
    e.currentTarget.classList.remove("dragging");
    dragSrcIndex = null;
  }

  function handleDrop(targetIndex, phaseId) {
    if (dragSrcIndex !== null) {
      // Reorder within sequence
      if (dragSrcIndex === targetIndex) return;
      const [moved] = sequence.splice(dragSrcIndex, 1);
      sequence.splice(targetIndex > dragSrcIndex ? targetIndex - 1 : targetIndex, 0, moved);
    } else {
      // New phase from palette
      if (sequence.includes(phaseId)) return;
      sequence.splice(targetIndex, 0, phaseId);
    }
    renderSequence();
    renderPalette(el("palette-search")?.value || "");
    markDirty();
  }

  // ── Drop on canvas background ────────────────────────────────────────────
  function bindCanvasDrop() {
    const area = el("phase-drop-area");
    if (!area) return;
    area.addEventListener("dragover", (e) => e.preventDefault());
    area.addEventListener("drop", (e) => {
      e.preventDefault();
      const phaseId = e.dataTransfer.getData("text/plain");
      if (phaseId && dragSrcIndex === null) addPhaseToSequence(phaseId);
    });
  }

  // ── Pipeline list ────────────────────────────────────────────────────────
  function renderPipelineList() {
    const listEl = el("pipeline-list");
    if (!listEl) return;
    listEl.innerHTML = "";

    if (!pipelines.length) {
      listEl.innerHTML = '<div style="padding:12px;color:var(--text-secondary);font-size:0.82rem">No pipelines yet</div>';
      return;
    }

    for (const p of pipelines) {
      const item = document.createElement("div");
      item.className = "pipeline-item" + (currentPipeline?.id === p.id ? " active" : "");
      item.dataset.id = p.id;
      item.innerHTML = `
        <div class="pip-name">${p.name}${p.builtin ? ' <span class="pip-builtin">built-in</span>' : ""}</div>
        <div class="pip-phases">${p.phases.length} phases</div>
      `;
      item.addEventListener("click", () => loadPipelineIntoBuilder(p));
      listEl.appendChild(item);
    }
  }

  function loadPipelineIntoBuilder(pipeline) {
    currentPipeline = pipeline;
    sequence = [...(pipeline.phases || [])];
    el("pipeline-name-input").value = pipeline.name;
    el("pipeline-desc-input").value = pipeline.description || "";
    el("save-pipeline-btn").classList.remove("btn-pulse");
    renderPipelineList();
    renderSequence();
    renderPalette(el("palette-search")?.value || "");
    hidePipelineLog();
  }

  function newPipeline() {
    currentPipeline = null;
    sequence = [];
    el("pipeline-name-input").value = "";
    el("pipeline-desc-input").value = "";
    el("save-pipeline-btn").classList.remove("btn-pulse");
    renderPipelineList();
    renderSequence();
    renderPalette();
    hidePipelineLog();
  }

  // ── Save ─────────────────────────────────────────────────────────────────
  async function savePipeline() {
    const name = el("pipeline-name-input").value.trim();
    if (!name) { alert("Enter a pipeline name."); return; }
    if (!sequence.length) { alert("Add at least one phase."); return; }

    const body = {
      name,
      phases: sequence,
      description: el("pipeline-desc-input").value.trim(),
    };

    try {
      let saved;
      if (currentPipeline && !currentPipeline.builtin) {
        saved = await apiFetch(`/api/pipelines/${currentPipeline.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
      } else {
        saved = await apiFetch("/api/pipelines", {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      await loadPipelines();
      currentPipeline = saved;
      el("save-pipeline-btn").classList.remove("btn-pulse");
      renderPipelineList();
    } catch (err) {
      alert("Save failed: " + err.message);
    }
  }

  // ── Run ──────────────────────────────────────────────────────────────────
  function showRunConfig() {
    el("run-config").style.display = "block";
  }

  function hideRunConfig() {
    el("run-config").style.display = "none";
  }

  async function confirmRun() {
    hideRunConfig();
    if (!currentPipeline) {
      alert("Save the pipeline first.");
      return;
    }
    const projectPath = el("project-path-input").value.trim();
    startRun(currentPipeline.id, projectPath);
  }

  function startRun(pipelineId, projectPath) {
    if (activeSSE) { activeSSE.close(); activeSSE = null; }

    // Show log panel
    el("pipeline-log").style.display = "flex";
    const logPhases = el("log-phases");
    logPhases.innerHTML = "";
    el("log-title").textContent = `Running: ${currentPipeline?.name || "pipeline"}`;
    el("log-status").textContent = "";
    el("log-status").style.color = "";

    // Initialize phase rows (pending state)
    for (const phaseId of sequence) {
      const meta = allPhases.find((p) => p.id === phaseId) || { label: phaseId };
      const row = document.createElement("div");
      row.className = "log-phase-row pending";
      row.id = `lpr-${phaseId}`;
      row.innerHTML = `
        <span class="lpr-icon">○</span>
        <span class="lpr-label">${meta.label}</span>
        <span class="lpr-dur"></span>
      `;
      logPhases.appendChild(row);
    }

    // SSE via fetch (POST body)
    fetch(`/api/pipelines/${pipelineId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ project_path: projectPath }),
    }).then((response) => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const evt = JSON.parse(line.slice(6));
                handleSSEEvent(evt);
              } catch { /* ignore parse errors */ }
            }
          }
          read();
        });
      }
      read();
    }).catch((err) => {
      el("log-status").textContent = "Connection error: " + err.message;
      el("log-status").style.color = "#ef4444";
    });
  }

  function handleSSEEvent(evt) {
    if (evt.type === "phase_started") {
      const row = document.getElementById(`lpr-${evt.phase}`);
      if (row) {
        row.className = "log-phase-row running";
        row.querySelector(".lpr-icon").textContent = "⟳";
      }
    } else if (evt.type === "phase_done") {
      const row = document.getElementById(`lpr-${evt.phase}`);
      if (row) {
        row.className = "log-phase-row done";
        row.querySelector(".lpr-icon").textContent = "✓";
        row.querySelector(".lpr-dur").textContent = evt.duration ? `${evt.duration}s` : "";
      }
    } else if (evt.type === "phase_error") {
      const row = document.getElementById(`lpr-${evt.phase}`);
      if (row) {
        row.className = "log-phase-row error";
        row.querySelector(".lpr-icon").textContent = "✗";
        // Append error message
        const errSpan = document.createElement("span");
        errSpan.className = "lpr-error";
        errSpan.textContent = " " + (evt.error || "Failed");
        row.appendChild(errSpan);
      }
    } else if (evt.type === "run_finished") {
      const logStatus = el("log-status");
      if (evt.status === "completed") {
        logStatus.textContent = "✓ Completed";
        logStatus.style.color = "#10b981";
      } else {
        logStatus.textContent = "✗ Failed";
        logStatus.style.color = "#ef4444";
      }
      // Refresh run history
      loadPipelines().then(() => renderPipelineList());
    }
  }

  function hidePipelineLog() {
    el("pipeline-log").style.display = "none";
    if (activeSSE) { activeSSE.close(); activeSSE = null; }
  }

  // ── Button bindings ──────────────────────────────────────────────────────
  function bindButtons() {
    el("new-pipeline-btn")?.addEventListener("click", newPipeline);
    el("save-pipeline-btn")?.addEventListener("click", savePipeline);
    el("run-pipeline-btn")?.addEventListener("click", showRunConfig);
    el("confirm-run-btn")?.addEventListener("click", confirmRun);
    el("cancel-run-btn")?.addEventListener("click", hideRunConfig);
    el("close-log-btn")?.addEventListener("click", hidePipelineLog);
    el("palette-search")?.addEventListener("input", (e) => renderPalette(e.target.value));
    bindCanvasDrop();
  }

  return { init };
})();

// Auto-init when fragment loads
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("pipeline-view")) {
    PipelineApp.init().catch(console.error);
  }
});

// Support SPA fragment injection
if (document.getElementById("pipeline-view")) {
  PipelineApp.init().catch(console.error);
}
