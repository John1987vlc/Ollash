/**
 * Human-in-the-loop (HIL) Approval Center Logic
 */

const HILModule = (function() {
    // --- State ---
    let pendingRequests = [];
    let selectedRequestId = null;

    // --- Elements ---
    let requestList, detailsArea, emptyDetailsArea, pendingCount;
    let detailsTitle, detailsType, detailsMeta, detailsContent, feedbackInput;
    let approveBtn, rejectBtn, modifyBtn, refreshBtn;

    function init() {
        console.log("Initializing HILModule...");
        
        // Cache elements
        requestList = document.getElementById('hil-request-list');
        detailsArea = document.getElementById('hil-details-area');
        emptyDetailsArea = document.getElementById('hil-empty-details');
        pendingCount = document.getElementById('hil-pending-count');
        
        detailsTitle = document.getElementById('details-title');
        detailsType = document.getElementById('details-type');
        detailsMeta = document.getElementById('details-meta');
        detailsContent = document.getElementById('details-content-pre');
        feedbackInput = document.getElementById('hil-feedback');
        
        approveBtn = document.getElementById('hil-approve-btn');
        rejectBtn = document.getElementById('hil-reject-btn');
        modifyBtn = document.getElementById('hil-modify-btn');
        refreshBtn = document.getElementById('refresh-hil-btn');

        // Events
        if (approveBtn) approveBtn.addEventListener('click', () => submitResponse('approve'));
        if (rejectBtn) rejectBtn.addEventListener('click', () => submitResponse('reject'));
        if (modifyBtn) modifyBtn.addEventListener('click', () => submitResponse('correct'));
        if (refreshBtn) refreshBtn.addEventListener('click', fetchPendingRequests);

        // Initial Load
        fetchPendingRequests();
        
        // Poll for new requests every 30 seconds
        setInterval(fetchPendingRequests, 30000);
    }

    async function fetchPendingRequests() {
        try {
            const response = await fetch('/api/hil/pending');
            const data = await response.json();
            pendingRequests = data;
            
            updateInbox();
            updateBadge();
        } catch (error) {
            console.error("Failed to fetch pending requests:", error);
        }
    }

    function updateInbox() {
        if (!requestList) return;

        if (pendingRequests.length === 0) {
            requestList.innerHTML = `
                <div class="empty-state">
                    <p>No hay solicitudes pendientes.</p>
                </div>
            `;
            showEmptyDetails();
            return;
        }

        requestList.innerHTML = '';
        pendingRequests.forEach(req => {
            const div = document.createElement('div');
            div.className = `hil-request-item ${selectedRequestId === req.id ? 'active' : ''}`;
            div.onclick = () => selectRequest(req.id);
            
            const timeStr = new Date(req.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            div.innerHTML = `
                <span class="item-title">${req.title}</span>
                <div class="item-meta">
                    <span class="badge sm info">${req.type}</span>
                    <span>${req.agent}</span> • <span>${timeStr}</span>
                </div>
            `;
            requestList.appendChild(div);
        });

        // Keep current selection if it still exists
        const current = pendingRequests.find(r => r.id === selectedRequestId);
        if (!current) {
            showEmptyDetails();
        } else {
            displayDetails(current);
        }
    }

    function updateBadge() {
        if (pendingCount) {
            pendingCount.textContent = pendingRequests.length;
            pendingCount.style.display = pendingRequests.length > 0 ? 'inline-block' : 'none';
        }
    }

    function selectRequest(requestId) {
        selectedRequestId = requestId;
        
        // Update selection UI in list
        const items = requestList.querySelectorAll('.hil-request-item');
        items.forEach((item, index) => {
            item.classList.toggle('active', pendingRequests[index].id === requestId);
        });

        const req = pendingRequests.find(r => r.id === requestId);
        if (req) {
            displayDetails(req);
        }
    }

    function displayDetails(req) {
        detailsArea.style.display = 'flex';
        emptyDetailsArea.style.display = 'none';

        detailsTitle.textContent = req.title;
        detailsType.textContent = req.type;
        detailsMeta.textContent = `Agente: ${req.agent} | Solicitado: ${new Date(req.timestamp).toLocaleString()}`;
        
        // Render detailed content
        let contentStr = "";
        if (typeof req.details === 'object') {
            contentStr = JSON.stringify(req.details, null, 2);
        } else {
            contentStr = req.details;
        }
        detailsContent.textContent = contentStr;
        
        // Highlight if highlight.js is present
        if (window.hljs) {
            window.hljs.highlightElement(detailsContent);
        }

        feedbackInput.value = '';
    }

    function showEmptyDetails() {
        detailsArea.style.display = 'none';
        emptyDetailsArea.style.display = 'flex';
        selectedRequestId = null;
    }

    async function submitResponse(responseType) {
        if (!selectedRequestId) return;

        const feedback = feedbackInput.value.trim();
        if ((responseType === 'reject' || responseType === 'correct') && !feedback) {
            NotificationService.warning("Por favor, proporciona retroalimentación para explicar la decisión.");
            return;
        }

        const btn = document.getElementById(`hil-${responseType}-btn`);
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "Procesando...";

        try {
            const response = await fetch('/api/hil/respond', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request_id: selectedRequestId,
                    response: responseType,
                    feedback: feedback
                })
            });

            const data = await response.json();
            if (data.status === 'success') {
                NotificationService.success(`Decisión enviada: ${responseType}`);
                // Remove from local list and UI
                pendingRequests = pendingRequests.filter(r => r.id !== selectedRequestId);
                selectedRequestId = null;
                updateInbox();
                updateBadge();
            } else {
                NotificationService.error("Error al enviar la decisión: " + data.error);
            }
        } catch (error) {
            NotificationService.error("Error de red al procesar la aprobación.");
        } finally {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }

    return {
        init: init,
        refresh: fetchPendingRequests
    };
})();

// Register on load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('hil-view')) {
        HILModule.init();
    }
});
