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

type Subscriber<T = unknown> = (value: T) => void;

export interface OllashStoreAPI {
    get<T = unknown>(key: string): T | undefined;
    set<T = unknown>(key: string, value: T): void;
    subscribe<T = unknown>(key: string, fn: Subscriber<T>): void;
    unsubscribe(key: string, fn: Subscriber): void;
    snapshot(): Record<string, unknown>;
}

declare global {
    interface Window {
        OllashStore: OllashStoreAPI;
    }
}

window.OllashStore = (function (): OllashStoreAPI {
    'use strict';

    const _state: Record<string, unknown> = {};
    const _listeners: Record<string, Subscriber[]> = {};

    function get<T = unknown>(key: string): T | undefined {
        return _state[key] as T | undefined;
    }

    function set<T = unknown>(key: string, value: T): void {
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

    function subscribe<T = unknown>(key: string, fn: Subscriber<T>): void {
        if (!_listeners[key]) {
            _listeners[key] = [];
        }
        if (!_listeners[key].includes(fn as Subscriber)) {
            _listeners[key].push(fn as Subscriber);
        }
        if (key in _state) {
            try {
                fn(_state[key] as T);
            } catch (e) {
                console.error('[OllashStore] Error in initial emit for "' + key + '":', e);
            }
        }
    }

    function unsubscribe(key: string, fn: Subscriber): void {
        if (_listeners[key]) {
            _listeners[key] = _listeners[key].filter(function (h) { return h !== fn; });
        }
    }

    function snapshot(): Record<string, unknown> {
        return Object.assign({}, _state);
    }

    return { get, set, subscribe, unsubscribe, snapshot };
}());
