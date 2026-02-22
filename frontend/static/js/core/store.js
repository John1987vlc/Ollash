/**
 * OllashStore — Centralized pub/sub state management.
 *
 * A lightweight observer-pattern store that provides a single source of truth
 * for shared UI state (active theme, sidebar state, active session, etc.).
 * Replaces ad-hoc window.* globals scattered across modules.
 *
 * Usage:
 *   OllashStore.set('theme', 'dark');
 *   OllashStore.get('theme');           // → 'dark'
 *   OllashStore.subscribe('theme', (value) => console.log('Theme:', value));
 *   OllashStore.unsubscribe('theme', handler);
 */
window.OllashStore = (function () {
    'use strict';

    /** @type {Object.<string, *>} */
    const _state = {};

    /** @type {Object.<string, Function[]>} */
    const _listeners = {};

    /**
     * Get the current value for a state key.
     * @param {string} key
     * @returns {*}
     */
    function get(key) {
        return _state[key];
    }

    /**
     * Set a value and notify all subscribers for that key.
     * @param {string} key
     * @param {*} value
     */
    function set(key, value) {
        _state[key] = value;
        const handlers = _listeners[key];
        if (handlers) {
            handlers.slice().forEach(function (fn) {
                try {
                    fn(value);
                } catch (e) {
                    console.error('[OllashStore] Error in subscriber for "' + key + '":', e);
                }
            });
        }
    }

    /**
     * Subscribe to changes for a state key.
     * The callback is invoked immediately with the current value (if set),
     * then on every subsequent set().
     * @param {string} key
     * @param {function(*): void} fn
     */
    function subscribe(key, fn) {
        if (!_listeners[key]) {
            _listeners[key] = [];
        }
        if (!_listeners[key].includes(fn)) {
            _listeners[key].push(fn);
        }
        // Emit current value immediately if available
        if (key in _state) {
            try {
                fn(_state[key]);
            } catch (e) {
                console.error('[OllashStore] Error in initial emit for "' + key + '":', e);
            }
        }
    }

    /**
     * Unsubscribe a previously registered handler.
     * @param {string} key
     * @param {function(*): void} fn
     */
    function unsubscribe(key, fn) {
        if (_listeners[key]) {
            _listeners[key] = _listeners[key].filter(function (h) { return h !== fn; });
        }
    }

    /**
     * Return a snapshot of all current state (for debugging).
     * @returns {Object}
     */
    function snapshot() {
        return Object.assign({}, _state);
    }

    return { get, set, subscribe, unsubscribe, snapshot };
}());
