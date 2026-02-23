/**
 * NotificationToast — Lightweight in-page toast notification component.
 *
 * Extracted from alert-handler.js so the DOM insertion / animation logic
 * can be reused independently of the SSE alert stream.
 *
 * Usage:
 *   NotificationToast.show('Operation complete', 'success');
 *   NotificationToast.show('Something failed', 'error', { duration: 8000 });
 *   NotificationToast.show('Please wait…', 'info', { duration: 0 }); // persistent
 *
 * Types: 'success' | 'error' | 'warning' | 'info'
 *
 * Container:
 *   The component auto-creates a #notification-container div if one doesn't
 *   exist. It is appended to document.body at the top-right.
 */
window.NotificationToast = (function () {
    'use strict';

    const CONTAINER_ID = 'notification-container';
    const DEFAULT_DURATION = 8000;  // ms (increased from 5000)
    const MAX_VISIBLE = 5;

    const ICONS = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ',
    };

    /**
     * Get or create the notification container element.
     * @returns {HTMLElement}
     */
    function _getContainer() {
        let container = document.getElementById(CONTAINER_ID);
        if (!container) {
            container = document.createElement('div');
            container.id = CONTAINER_ID;
            container.setAttribute('aria-live', 'polite');
            container.setAttribute('aria-atomic', 'false');
            container.setAttribute('role', 'region');
            container.setAttribute('aria-label', 'Notifications');
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Sanitize a string to prevent XSS when inserted as textContent.
     * @param {string} text
     * @returns {string}
     */
    function _sanitize(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /**
     * Show a toast notification.
     * @param {string} message   - Text content of the notification.
     * @param {'success'|'error'|'warning'|'info'} [type='info']
     * @param {{ duration?: number, title?: string }} [options]
     * @returns {HTMLElement}    - The created toast element.
     */
    function show(message, type, options) {
        type = type || 'info';
        options = options || {};
        const duration = options.duration !== undefined ? options.duration : DEFAULT_DURATION;

        const container = _getContainer();

        // Evict oldest toast if at capacity
        const existing = container.querySelectorAll('.notification-toast');
        if (existing.length >= MAX_VISIBLE) {
            existing[0].remove();
        }

        // Build toast element
        const toast = document.createElement('div');
        toast.className = 'notification-toast notification-toast--' + type;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');

        const icon = document.createElement('span');
        icon.className = 'notification-toast__icon';
        icon.textContent = ICONS[type] || ICONS.info;
        icon.setAttribute('aria-hidden', 'true');

        const body = document.createElement('div');
        body.className = 'notification-toast__body';

        if (options.title) {
            const titleEl = document.createElement('strong');
            titleEl.className = 'notification-toast__title';
            titleEl.textContent = options.title;
            body.appendChild(titleEl);
        }

        const msgEl = document.createElement('p');
        msgEl.className = 'notification-toast__message';
        msgEl.textContent = message;  // textContent prevents XSS
        body.appendChild(msgEl);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'notification-toast__close';
        closeBtn.setAttribute('aria-label', 'Dismiss notification');
        closeBtn.textContent = '×';
        closeBtn.addEventListener('click', function () { _dismiss(toast); });

        toast.appendChild(icon);
        toast.appendChild(body);
        toast.appendChild(closeBtn);

        container.appendChild(toast);

        // Animate in (requestAnimationFrame ensures the class is applied after paint)
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                toast.classList.add('notification-toast--visible');
            });
        });

        // Auto-dismiss
        if (duration > 0) {
            setTimeout(function () { _dismiss(toast); }, duration);
        }

        return toast;
    }

    /**
     * Dismiss a toast with an exit animation.
     * @param {HTMLElement} toast
     */
    function _dismiss(toast) {
        if (!toast || !toast.parentNode) return;
        toast.classList.remove('notification-toast--visible');
        toast.classList.add('notification-toast--hiding');
        toast.addEventListener('transitionend', function handler() {
            toast.removeEventListener('transitionend', handler);
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, { once: true });
        // Fallback removal if transition doesn't fire
        setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 600);
    }

    /**
     * Dismiss all visible toasts.
     */
    function dismissAll() {
        const container = document.getElementById(CONTAINER_ID);
        if (!container) return;
        container.querySelectorAll('.notification-toast').forEach(_dismiss);
    }

    return { show, dismissAll };
}());
