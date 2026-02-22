/**
 * Ollash Knowledge Base & Memory Manager
 * Manages vector docs, episodic memory, and error patterns.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Tab switching logic
    const tabs = document.querySelectorAll('.k-tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.onclick = () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            const target = tab.dataset.tab;
            document.getElementById(`${target}-tab`).classList.add('active');
            
            // Refresh data based on tab
            if (target === 'episodic') loadEpisodicMemory();
            if (target === 'errors') loadErrorKnowledge();
            if (target === 'vector') loadVectorDocs();
        };
    });

    // --- Vector Documents (RAG) ---
    const kbDocGrid = document.getElementById('kb-doc-grid');
    const kbFileInput = document.getElementById('kb-file-input');
    const kbUploadZone = document.getElementById('kb-upload-zone');

    async function loadVectorDocs() {
        kbDocGrid.innerHTML = '<p class="placeholder">Loading knowledge base...</p>';
        try {
            const response = await fetch('/api/knowledge/documents');
            const data = await response.json();
            
            if (data.documents && data.documents.length > 0) {
                kbDocGrid.innerHTML = '';
                data.documents.forEach(doc => {
                    const card = document.createElement('div');
                    card.className = 'kb-card';
                    card.innerHTML = `
                        <div class="kb-card-icon">&#x1f4d1;</div>
                        <div class="kb-card-info">
                            <span class="kb-card-name">${doc.filename}</span>
                            <span class="kb-card-source">${doc.source}</span>
                        </div>
                        <button class="kb-card-delete" onclick="deleteDoc('${doc.id}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    `;
                    kbDocGrid.appendChild(card);
                });
            } else {
                kbDocGrid.innerHTML = '<p class="placeholder">No documents indexed yet.</p>';
            }
        } catch (error) {
            console.error('Error loading vector docs:', error);
            kbDocGrid.innerHTML = '<p class="placeholder">Failed to load knowledge base.</p>';
        }
    }

    // --- Episodic Memory ---
    const episodicStats = document.getElementById('episodic-stats');
    const episodicList = document.getElementById('episodic-list');

    async function loadEpisodicMemory() {
        episodicList.innerHTML = '<p class="placeholder">Loading episodic memory...</p>';
        try {
            const response = await fetch('/api/knowledge/episodes');
            const data = await response.json();
            
            // Render Stats
            const stats = data.statistics;
            episodicStats.innerHTML = `
                <div class="stat-item"><div class="stat-val">${stats.total_episodes}</div><div class="stat-label">Episodes</div></div>
                <div class="stat-item"><div class="stat-val">${stats.successful_solutions}</div><div class="stat-label">Solutions</div></div>
                <div class="stat-item"><div class="stat-val">${(stats.success_rate * 100).toFixed(1)}%</div><div class="stat-label">Success Rate</div></div>
                <div class="stat-item"><div class="stat-val">${stats.total_decisions}</div><div class="stat-label">Decisions</div></div>
            `;

            // Render Episodes
            if (data.episodes && data.episodes.length > 0) {
                episodicList.innerHTML = '';
                data.episodes.forEach(ep => {
                    const card = document.createElement('div');
                    card.className = 'memory-card';
                    card.innerHTML = `
                        <span class="badge ${ep.outcome}">${ep.outcome.toUpperCase()}</span>
                        <h4>${ep.error_type}</h4>
                        <p>${ep.error_description.substring(0, 100)}...</p>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">
                            Project: ${ep.project_name} | Phase: ${ep.phase_name}
                        </div>
                    `;
                    episodicList.appendChild(card);
                });
            } else {
                episodicList.innerHTML = '<p class="placeholder">No episodic memory recorded.</p>';
            }
        } catch (error) {
            console.error('Error loading episodic memory:', error);
            episodicList.innerHTML = '<p class="placeholder">Failed to load episodic memory.</p>';
        }
    }

    // --- Error Knowledge Base ---
    const errorStats = document.getElementById('error-stats');
    const errorList = document.getElementById('error-list');

    async function loadErrorKnowledge() {
        errorList.innerHTML = '<p class="placeholder">Loading error patterns...</p>';
        try {
            const response = await fetch('/api/knowledge/errors');
            const data = await response.json();
            
            // Render Stats
            const stats = data.statistics;
            errorStats.innerHTML = `
                <div class="stat-item"><div class="stat-val">${stats.total_patterns}</div><div class="stat-label">Unique Patterns</div></div>
                <div class="stat-item"><div class="stat-val">${stats.total_errors}</div><div class="stat-label">Errors Tracked</div></div>
                <div class="stat-item"><div class="stat-val">${Object.keys(stats.by_language).length}</div><div class="stat-label">Languages</div></div>
            `;

            // Render Patterns
            if (data.patterns && data.patterns.length > 0) {
                errorList.innerHTML = '';
                data.patterns.forEach(p => {
                    const card = document.createElement('div');
                    card.className = 'memory-card';
                    card.innerHTML = `
                        <span class="badge ${p.severity}">${p.severity.toUpperCase()}</span>
                        <h4>${p.error_type} - ${p.language}</h4>
                        <p><strong>Description:</strong> ${p.description}</p>
                        <p><strong>Immunity Tip:</strong> ${p.prevention_tip}</p>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">
                            Frequency: ${p.frequency} | Last seen: ${new Date(p.last_encountered).toLocaleDateString()}
                        </div>
                    `;
                    errorList.appendChild(card);
                });
            } else {
                errorList.innerHTML = '<p class="placeholder">No error patterns learned yet.</p>';
            }
        } catch (error) {
            console.error('Error loading error knowledge:', error);
            errorList.innerHTML = '<p class="placeholder">Failed to load error immunity base.</p>';
        }
    }

    // --- Upload Handlers ---
    if (kbUploadZone) {
        kbUploadZone.onclick = () => kbFileInput.click();
        kbFileInput.onchange = handleUpload;
        
        kbUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            kbUploadZone.classList.add('active');
        });
        
        kbUploadZone.addEventListener('dragleave', () => {
            kbUploadZone.classList.remove('active');
        });
        
        kbUploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            kbUploadZone.classList.remove('active');
            const files = e.dataTransfer.files;
            if (files.length > 0) handleFiles(files);
        });
    }

    async function handleUpload() {
        const files = kbFileInput.files;
        if (files.length > 0) handleFiles(files);
    }

    async function handleFiles(files) {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('/api/knowledge/upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (result.status === 'success') {
                    // Refresh current view if it's vector
                    if (document.querySelector('.k-tab.active').dataset.tab === 'vector') {
                        loadVectorDocs();
                    }
                }
            } catch (error) {
                console.error('Upload failed:', error);
            }
        }
    }

    // Initial load
    loadVectorDocs();
});
