/**
 * Proactive Alert Handler for Ollash
 * Listens for real-time system alerts and displays notifications
 */

class ProactiveAlertHandler {
    constructor() {
        this.eventSource = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000; // 3 seconds
        this.alertMap = new Map();
        this.alertHistory = [];
        this.maxHistorySize = 100;
    }

    /**
     * Connect to the SSE alert stream
     */
    connect() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        try {
            this.eventSource = new EventSource('/api/alerts/stream');

            // Connection established
            this.eventSource.addEventListener('open', (e) => {
                console.log('✅ Connected to alert stream');
                this.isConnected = true;
                this.reconnectAttempts = 0;
            });

            // Handle ui_alert events (proactive notifications from the system)
            this.eventSource.addEventListener('ui_alert', (e) => {
                this.handleUIAlert(e.data);
            });

            // Handle alert_triggered events from AutomationManager
            this.eventSource.addEventListener('alert_triggered', (e) => {
                this.handleAlertTriggered(e.data);
            });

            // Handle automation events
            this.eventSource.addEventListener('task_execution_complete', (e) => {
                this.handleTaskComplete(e.data);
            });

            this.eventSource.addEventListener('task_execution_error', (e) => {
                this.handleTaskError(e.data);
            });

            // Handle errors
            this.eventSource.addEventListener('error', (e) => {
                this.handleSSEError();
            });

            this.eventSource.onerror = () => {
                this.handleSSEError();
            };

        } catch (error) {
            console.error('❌ Failed to connect to alert stream:', error);
            this.scheduleReconnect();
        }
    }

    /**
     * Handle UI alert from server
     */
    handleUIAlert(eventData) {
        try {
            const alertData = JSON.parse(eventData);
            
            // Display notification
            this.showNotification(
                alertData.title || alertData.message,
                alertData.message,
                alertData.type || 'info',
                alertData
            );

            // Play alert sound if critical
            if (alertData.type === 'critical') {
                this.playAlertSound('critical');
            }

        } catch (error) {
            console.error('Error parsing UI alert:', error);
        }
    }

    /**
     * Handle threshold-based alert triggering
     */
    handleAlertTriggered(eventData) {
        try {
            const alertInfo = JSON.parse(eventData);
            const alertId = alertInfo.alert_id;
            
            // Check if alert already shown recently
            const lastShown = this.alertMap.get(alertId);
            if (lastShown && (Date.now() - lastShown) < 60000) {
                // Alert shown in last 60 seconds, skip duplicate
                return;
            }

            this.alertMap.set(alertId, Date.now());

            // Build comprehensive message
            const messageLines = [
                `${alertInfo.name || alertId}`,
                `Entity: ${alertInfo.entity}`,
                `Current: ${alertInfo.current_value} | Threshold: ${alertInfo.threshold} (${alertInfo.operator})`
            ];

            const message = messageLines.join('\n');
            const severity = alertInfo.severity || 'warning';

            // Display notification
            this.showNotification(
                alertInfo.name || 'System Alert',
                message,
                severity,
                alertInfo
            );

            // Add to history
            this.addToHistory(alertInfo);

            // Play sound based on severity
            if (severity === 'critical') {
                this.playAlertSound('critical');
            } else if (severity === 'warning') {
                this.playAlertSound('warning');
            }

        } catch (error) {
            console.error('Error handling alert:', error);
        }
    }

    /**
     * Handle task completion event
     */
    handleTaskComplete(eventData) {
        try {
            const taskInfo = JSON.parse(eventData);
            const message = `✅ Task "${taskInfo.task_name}" completed successfully`;
            
            this.showNotification(
                'Task Complete',
                message,
                'success',
                taskInfo
            );
        } catch (error) {
            console.error('Error handling task complete:', error);
        }
    }

    /**
     * Handle task error event
     */
    handleTaskError(eventData) {
        try {
            const taskInfo = JSON.parse(eventData);
            const message = `❌ Task "${taskInfo.task_name}" failed: ${taskInfo.details}`;
            
            this.showNotification(
                'Task Error',
                message,
                'critical',
                taskInfo
            );

            this.playAlertSound('critical');
        } catch (error) {
            console.error('Error handling task error:', error);
        }
    }

    /**
     * Display notification on screen
     */
    showNotification(title, message, type = 'info', data = {}) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${this.sanitize(title)}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="notification-body">
                ${this.sanitize(message)}
            </div>
            ${data.alert_id ? `<div class="notification-meta">#${data.alert_id}</div>` : ''}
        `;

        // Add to notifications container
        let container = document.getElementById('notifications-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notifications-container';
            container.className = 'notifications-container';
            document.body.appendChild(container);
        }

        container.appendChild(notification);

        // Auto-dismiss after 5 seconds (or 8 seconds for critical)
        const dismissTime = type === 'critical' ? 8000 : 5000;
        setTimeout(() => {
            notification.classList.add('dismissing');
            setTimeout(() => notification.remove(), 300);
        }, dismissTime);
    }

    /**
     * Play alert sound
     */
    playAlertSound(severity = 'warning') {
        try {
            const audioContext = window.AudioContext || window.webkitAudioContext;
            if (!audioContext) return;

            const ctx = new audioContext();
            const oscillator = ctx.createOscillator();
            const gainNode = ctx.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);

            // Different tones for different severities
            if (severity === 'critical') {
                oscillator.frequency.value = 1000; // High frequency
                gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.3);
            } else if (severity === 'warning') {
                oscillator.frequency.value = 750;
                gainNode.gain.setValueAtTime(0.05, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.2);
            }
        } catch (error) {
            console.warn('Could not play alert sound:', error);
        }
    }

    /**
     * Add alert to history
     */
    addToHistory(alertInfo) {
        this.alertHistory.unshift({
            ...alertInfo,
            timestamp: new Date().toISOString()
        });

        if (this.alertHistory.length > this.maxHistorySize) {
            this.alertHistory.pop();
        }

        // Update dashboard if available
        if (typeof window.updateAlertHistory === 'function') {
            window.updateAlertHistory(this.alertHistory);
        }
    }

    /**
     * Handle SSE connection error
     */
    handleSSEError() {
        this.isConnected = false;
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.scheduleReconnect();
    }

    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.warn('❌ Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`⏳ Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Sanitize HTML
     */
    sanitize(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get alert history
     */
    getHistory(limit = 50) {
        return this.alertHistory.slice(0, limit);
    }

    /**
     * Disconnect
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.isConnected = false;
    }
}

// Initialize globally when DOM is ready
let proactiveAlertHandler = null;

document.addEventListener('DOMContentLoaded', () => {
    proactiveAlertHandler = new ProactiveAlertHandler();
    proactiveAlertHandler.connect();
});

// Add CSS for notifications dynamically
function initNotificationStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .notifications-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
        }

        .notification {
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            padding: 16px;
            animation: slideIn 0.3s ease-out;
            border-left: 4px solid #3b82f6;
        }

        .notification.notification-info {
            border-left-color: #3b82f6;
        }

        .notification.notification-warning {
            border-left-color: #f59e0b;
            background: #fef3c7;
        }

        .notification.notification-critical {
            border-left-color: #ef4444;
            background: #fee2e2;
        }

        .notification.notification-success {
            border-left-color: #10b981;
            background: #f0fdf4;
        }

        .notification.dismissing {
            animation: slideOut 0.3s ease-in forwards;
        }

        .notification-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .notification-title {
            font-weight: 600;
            font-size: 14px;
        }

        .notification-close {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #9ca3af;
            padding: 0;
            margin: 0;
        }

        .notification-close:hover {
            color: #374151;
        }

        .notification-body {
            font-size: 13px;
            color: #4b5563;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .notification-meta {
            font-size: 11px;
            color: #9ca3af;
            margin-top: 8px;
            font-family: monospace;
        }

        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }

        @media (max-width: 640px) {
            .notifications-container {
                left: 10px;
                right: 10px;
                max-width: none;
            }

            .notification {
                padding: 12px;
            }

            .notification-title {
                font-size: 13px;
            }

            .notification-body {
                font-size: 12px;
            }
        }
    `;
    document.head.appendChild(style);
}

// Initialize styles when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotificationStyles);
} else {
    initNotificationStyles();
}
