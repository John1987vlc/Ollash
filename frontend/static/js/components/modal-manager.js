/**
 * ModalManager — Centralizes open/close logic for all modal dialogs.
 *
 * Replaces the scattered `window.closeXxxModal()` globals in main.js and
 * page modules. Each modal must have:
 *   - An id attribute matching the key used in open/close calls.
 *   - role="dialog" and aria-modal="true" (for accessibility).
 *   - A close trigger: [data-modal-close] or [data-modal-dismiss].
 *
 * Usage:
 *   ModalManager.open('automation-modal');
 *   ModalManager.close('automation-modal');
 *   ModalManager.closeAll();
 *   ModalManager.toggle('notification-modal');
 *
 * Auto-wiring:
 *   Elements with [data-modal-open="modal-id"] open the target modal on click.
 *   Elements with [data-modal-close] or [data-modal-dismiss] close the nearest
 *   ancestor modal.
 */
window.ModalManager = (function () {
    'use strict';

    const ACTIVE_CLASS = 'modal--open';
    const BODY_CLASS = 'body--modal-open';

    /** @type {string|null} Currently focused element before modal opened */
    let _previousFocus = null;

    /**
     * Resolve a modal element from id or element reference.
     * @param {string|HTMLElement} idOrEl
     * @returns {HTMLElement|null}
     */
    function _resolve(idOrEl) {
        if (typeof idOrEl === 'string') {
            return document.getElementById(idOrEl);
        }
        return idOrEl instanceof HTMLElement ? idOrEl : null;
    }

    /**
     * Open a modal by id.
     * @param {string|HTMLElement} idOrEl
     */
    function open(idOrEl) {
        const modal = _resolve(idOrEl);
        if (!modal) {
            console.warn('[ModalManager] Modal not found:', idOrEl);
            return;
        }

        // Save focus origin for restoration on close
        _previousFocus = document.activeElement;

        modal.style.display = 'flex';
        modal.classList.add(ACTIVE_CLASS);
        document.body.classList.add(BODY_CLASS);

        // Move focus into modal (first focusable element or the modal itself)
        const firstFocusable = modal.querySelector(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (firstFocusable) {
            firstFocusable.focus();
        } else {
            modal.setAttribute('tabindex', '-1');
            modal.focus();
        }

        // Notify store
        if (window.OllashStore) {
            OllashStore.set('openModal', modal.id || null);
        }
    }

    /**
     * Close a modal by id. If no id given, closes the topmost open modal.
     * @param {string|HTMLElement} [idOrEl]
     */
    function close(idOrEl) {
        let modal;
        if (idOrEl) {
            modal = _resolve(idOrEl);
        } else {
            // Find the most recently opened modal
            modal = document.querySelector('.modal.' + ACTIVE_CLASS);
        }

        if (!modal) return;

        modal.style.display = 'none';
        modal.classList.remove(ACTIVE_CLASS);

        // Remove body lock only if no other modals are open
        if (!document.querySelector('.modal.' + ACTIVE_CLASS)) {
            document.body.classList.remove(BODY_CLASS);
        }

        // Restore focus
        if (_previousFocus && document.contains(_previousFocus)) {
            _previousFocus.focus();
            _previousFocus = null;
        }

        if (window.OllashStore) {
            OllashStore.set('openModal', null);
        }
    }

    /**
     * Close all open modals.
     */
    function closeAll() {
        document.querySelectorAll('.modal.' + ACTIVE_CLASS).forEach(function (m) {
            close(m);
        });
    }

    /**
     * Toggle a modal open/closed.
     * @param {string|HTMLElement} idOrEl
     */
    function toggle(idOrEl) {
        const modal = _resolve(idOrEl);
        if (!modal) return;
        if (modal.classList.contains(ACTIVE_CLASS)) {
            close(modal);
        } else {
            open(modal);
        }
    }

    /**
     * Wire up declarative [data-modal-open] and [data-modal-close] triggers
     * and Escape key listener. Safe to call multiple times.
     */
    function init() {
        // [data-modal-open="modal-id"] → open on click
        document.querySelectorAll('[data-modal-open]').forEach(function (trigger) {
            if (trigger.dataset.modalBound) return;
            trigger.addEventListener('click', function () {
                open(trigger.dataset.modalOpen);
            });
            trigger.dataset.modalBound = '1';
        });

        // [data-modal-close] or [data-modal-dismiss] → close nearest modal
        document.querySelectorAll('[data-modal-close], [data-modal-dismiss]').forEach(function (btn) {
            if (btn.dataset.modalCloseBound) return;
            btn.addEventListener('click', function () {
                const parentModal = btn.closest('.modal');
                if (parentModal) close(parentModal);
            });
            btn.dataset.modalCloseBound = '1';
        });

        // Close on overlay click (click directly on .modal backdrop, not on .modal-content)
        document.querySelectorAll('.modal').forEach(function (modal) {
            if (modal.dataset.overlayBound) return;
            modal.addEventListener('click', function (e) {
                if (e.target === modal) close(modal);
            });
            modal.dataset.overlayBound = '1';
        });

        // Escape key closes topmost modal
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') close();
        });
    }

    return { open, close, closeAll, toggle, init };
}());
