/**
 * Notifications Module for Ollash Agent
 * Handles global SSE alerts and toast notifications.
 */
window.NotificationsModule = (function() {
    let unreadCount = 0;
    let eventSource = null;

    function init() {
        const bell = document.getElementById('notification-bell');
        const list = document.getElementById('notification-list');

        // Subscribe to SSE events for real-time notifications
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/alerts/stream'); 
        
        eventSource.addEventListener('ui_alert', (e) => {
            const data = JSON.parse(e.data);
            addNotification(data);
            
            // If it's an approval request, show the HIL modal
            if (data.type === 'approval_request') {
                showApprovalModal(data);
            }
        });

        eventSource.addEventListener('alert_triggered', (e) => {
            const data = JSON.parse(e.data);
            addNotification({
                type: 'warning',
                title: 'System Alert',
                message: data.message
            });
        });

        console.log("🚀 NotificationsModule initialized");
    }

    function addNotification(data) {
        unreadCount++;
        updateBell();
        
        const list = document.getElementById('notification-list');
        if (list) {
            const item = document.createElement('div');
            item.className = `notification-item ${data.type || 'info'}`;
            item.innerHTML = `
                <div class="notification-title">${escapeHtml(data.title || 'Notification')}</div>
                <div class="notification-msg">${escapeHtml(data.message)}</div>
                <div class="notification-time">${new Date().toLocaleTimeString()}</div>
            `;
            list.prepend(item);
        }
        
        // Show as toast
        if (window.notificationService) {
            notificationService.info(data.message);
        }
    }

    function updateBell() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = unreadCount;
            badge.style.display = unreadCount > 0 ? 'block' : 'none';
        }
    }

    function showApprovalModal(data) {
        const modal = document.getElementById('hil-modal');
        if (!modal) return;
        
        const prompt = document.getElementById('hil-prompt');
        const reqId = document.getElementById('hil-request-id');
        
        if (prompt) prompt.textContent = data.message;
        if (reqId) reqId.value = data.request_id;
        modal.style.display = 'block';
    }

    return {
        init: init,
        addNotification: addNotification
    };
})();
