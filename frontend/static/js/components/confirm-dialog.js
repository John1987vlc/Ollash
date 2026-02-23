/**
 * ConfirmDialog — Replaces native window.confirm() with a custom modal.
 *
 * The modal HTML is expected to be present in modals.html with the id
 * "confirm-modal". It must contain:
 *   - #confirm-modal-message   : paragraph for the confirmation question
 *   - #confirm-modal-ok        : OK / confirm button
 *   - #confirm-modal-cancel    : Cancel button
 *
 * Usage (async):
 *   const confirmed = await ConfirmDialog.ask('Are you sure you want to delete?');
 *   if (confirmed) { ... }
 *
 * Usage (callback):
 *   ConfirmDialog.ask('Delete project?').then((yes) => { if (yes) doDelete(); });
 */
window.ConfirmDialog = (function () {
    'use strict';

    const MODAL_ID = 'confirm-modal';
    const MSG_ID = 'confirm-modal-message';
    const OK_ID = 'confirm-modal-ok';
    const CANCEL_ID = 'confirm-modal-cancel';

    /** @type {Function|null} Pending resolve callback */
    let _resolve = null;

    function _getEls() {
        return {
            modal: document.getElementById(MODAL_ID),
            message: document.getElementById(MSG_ID),
            ok: document.getElementById(OK_ID),
            cancel: document.getElementById(CANCEL_ID),
        };
    }

    function _respond(value) {
        const { modal } = _getEls();
        if (window.ModalManager) {
            ModalManager.close(MODAL_ID);
        } else if (modal) {
            modal.style.display = 'none';
        }
        if (_resolve) {
            const cb = _resolve;
            _resolve = null;
            cb(value);
        }
    }

    /**
     * Show the confirmation dialog with the given message.
     * @param {string} message
     * @returns {Promise<boolean>} Resolves true (OK) or false (Cancel / Escape).
     */
    function ask(message) {
        return new Promise(function (resolve) {
            _resolve = resolve;

            const { modal, message: msgEl, ok, cancel } = _getEls();
            if (!modal) {
                // Fallback to native confirm if modal isn't in DOM yet
                resolve(window.confirm(message));
                return;
            }

            if (msgEl) msgEl.textContent = message;

            // Wire buttons (once — guard against duplicate listeners)
            if (!ok.dataset.confirmBound) {
                ok.addEventListener('click', function () { _respond(true); });
                cancel.addEventListener('click', function () { _respond(false); });
                ok.dataset.confirmBound = '1';
            }

            if (window.ModalManager) {
                ModalManager.open(MODAL_ID);
            } else {
                modal.style.display = 'flex';
            }
        });
    }

    /**
     * Initialize keyboard handling (Escape → cancel).
     * Called automatically on DOMContentLoaded.
     */
    function init() {
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && _resolve) {
                _respond(false);
            }
        });
    }

    function close() {
        _respond(false);
    }

    return { ask, init, close };
}());

// Callback-style compatibility shims for any remaining onclick handlers
window.showConfirmModal = function(message, onConfirm) {
    ConfirmDialog.ask(message).then(function(confirmed) {
        if (confirmed && onConfirm) onConfirm();
    });
};
window.closeConfirmModal = function() { ConfirmDialog.close(); };
