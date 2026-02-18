/**
 * NotificationService - Centralized notification management
 * Supports toast notifications with different severity levels
 */

class NotificationService {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create container
        this.container = document.createElement('div');
        this.container.className = 'notification-container';
        this.container.id = 'notification-container';
        document.body.appendChild(this.container);
    }

    /**
     * Show a notification toast
     * @param {string} message - The message to display
     * @param {string} type - Type: 'info', 'warning', 'error', 'success'
     * @param {number} duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
     */
    show(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `notification-toast ${type}`;
        
        const icons = {
            info: '&#9432;',
            success: '&#10003;',
            warning: '&#9888;',
            error: '&#10005;'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-message">${this.escapeHtml(message)}</div>
            <button class="toast-close" aria-label="Close notification" onclick="this.closest('.notification-toast').remove()">
                <span>&#10005;</span>
            </button>
        `;
        
        this.container.appendChild(toast);
        
        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });
        
        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
        
        return toast;
    }

    /**
     * Show info notification
     */
    info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    }

    /**
     * Show success notification
     */
    success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    }

    /**
     * Show warning notification
     */
    warning(message, duration = 7000) {
        return this.show(message, 'warning', duration);
    }

    /**
     * Show error notification
     */
    error(message, duration = 0) {
        return this.show(message, 'error', duration);
    }

    /**
     * Request permission for desktop notifications
     */
    requestDesktopPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    /**
     * Show a desktop notification (falls back to toast if not permitted)
     * @param {string} title - Notification title
     * @param {string} body - Notification body text
     * @returns {Notification|HTMLElement}
     */
    showDesktop(title, body) {
        if ('Notification' in window && Notification.permission === 'granted') {
            const n = new Notification(title, {
                body: body,
                tag: 'ollash-notification',
            });
            setTimeout(() => n.close(), 10000);
            return n;
        }
        // Fallback to toast
        return this.show(body, 'success', 10000);
    }

    /**
     * Clear all notifications
     */
    clearAll() {
        const toasts = this.container.querySelectorAll('.notification-toast');
        toasts.forEach(toast => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        });
    }

    /**
     * Helper: Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// Initialize globally
const notificationService = new NotificationService();
