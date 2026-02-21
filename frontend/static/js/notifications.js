// Notifications logic
document.addEventListener('DOMContentLoaded', () => {
    let unreadCount = 0;
    const bell = document.getElementById('notification-bell'); // We need to add this to HTML
    const list = document.getElementById('notification-list');

    function addNotification(data) {
        unreadCount++;
        updateBell();
        
        const item = document.createElement('div');
        item.className = `notification-item ${data.type}`;
        item.innerHTML = `
            <div class="notification-title">${data.title}</div>
            <div class="notification-msg">${data.message}</div>
            <div class="notification-time">${new Date().toLocaleTimeString()}</div>
        `;
        list.prepend(item);
        
        // Show as toast if not looking at notifications
        showToast(data.message);
    }

    function updateBell() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = unreadCount;
            badge.style.display = unreadCount > 0 ? 'block' : 'none';
        }
    }

    // Subscribe to SSE events for real-time notifications
    const eventSource = new EventSource('/api/events'); // Assuming SSE endpoint exists
    eventSource.addEventListener('ui_alert', (e) => {
        const data = JSON.parse(e.data);
        addNotification(data);
        
        // If it's an approval request, show the HIL modal
        if (data.type === 'approval_request') {
            showApprovalModal(data);
        }
    });

    window.showApprovalModal = (data) => {
        const modal = document.getElementById('hil-modal'); // Need to add to HTML
        document.getElementById('hil-prompt').textContent = data.message;
        document.getElementById('hil-request-id').value = data.request_id;
        modal.style.display = 'block';
    };
});
