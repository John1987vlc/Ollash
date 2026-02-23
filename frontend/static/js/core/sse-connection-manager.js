/**
 * SSE Connection Manager
 * Handles Server-Sent Events connection, reconnection logic, and reconnect banner UI.
 * Extracted from alert-handler.js for single-responsibility separation.
 */
window.SSEConnectionManager = (function () {
    const MAX_RECONNECT_ATTEMPTS = 5;
    const BASE_RECONNECT_DELAY = 3000; // ms

    let _eventSource = null;
    let _isConnected = false;
    let _reconnectAttempts = 0;
    let _reconnectBanner = null;
    let _onEventCallback = null;
    let _onConnectCallback = null;
    let _onDisconnectCallback = null;

    function _showReconnectBanner() {
        if (_reconnectBanner) return;
        const banner = document.createElement('div');
        banner.id = 'sse-reconnect-banner';
        banner.setAttribute('role', 'alert');
        banner.setAttribute('aria-live', 'assertive');
        banner.style.cssText = [
            'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:9999',
            'background:#f59e0b', 'color:#1c1917', 'padding:8px 16px',
            'font-size:0.85rem', 'font-weight:600', 'text-align:center',
            'display:flex', 'align-items:center', 'justify-content:center', 'gap:8px'
        ].join(';');
        banner.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            <span id="sse-banner-text">Reconectando con el servidor de alertas…</span>
        `;
        document.body.prepend(banner);
        _reconnectBanner = banner;
    }

    function _hideReconnectBanner() {
        if (!_reconnectBanner) return;
        const banner = _reconnectBanner;
        banner.style.background = '#10b981';
        banner.querySelector('#sse-banner-text').textContent = 'Conexión con alertas restaurada';
        setTimeout(() => {
            banner.remove();
            _reconnectBanner = null;
        }, 2500);
    }

    function _handleError() {
        _isConnected = false;
        if (_eventSource) {
            _eventSource.close();
            _eventSource = null;
        }
        _showReconnectBanner();
        if (typeof _onDisconnectCallback === 'function') _onDisconnectCallback();
        _scheduleReconnect();
    }

    function _scheduleReconnect() {
        if (_reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            if (_reconnectBanner) {
                _reconnectBanner.style.background = '#ef4444';
                _reconnectBanner.style.color = '#fff';
                const txt = _reconnectBanner.querySelector('#sse-banner-text');
                if (txt) txt.textContent = 'No se pudo conectar con el servidor de alertas. Recarga la página.';
            }
            return;
        }

        _reconnectAttempts++;
        const delay = BASE_RECONNECT_DELAY * Math.pow(2, _reconnectAttempts - 1);

        if (_reconnectBanner) {
            const txt = _reconnectBanner.querySelector('#sse-banner-text');
            if (txt) txt.textContent = `Reconectando… (intento ${_reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`;
        }

        setTimeout(() => connect(_eventSource && _eventSource.url), delay);
    }

    function connect(url) {
        if (_eventSource) _eventSource.close();

        try {
            _eventSource = new EventSource(url || '/api/alerts/stream');

            _eventSource.addEventListener('open', () => {
                _isConnected = true;
                _reconnectAttempts = 0;
                _hideReconnectBanner();
                if (typeof _onConnectCallback === 'function') _onConnectCallback();
            });

            _eventSource.addEventListener('error', _handleError);
            _eventSource.onerror = _handleError;

            // Forward all named events to callback
            ['ui_alert', 'alert_triggered', 'task_execution_complete', 'task_execution_error'].forEach(eventType => {
                _eventSource.addEventListener(eventType, (e) => {
                    if (typeof _onEventCallback === 'function') {
                        _onEventCallback(eventType, e.data);
                    }
                });
            });

        } catch (err) {
            console.error('❌ SSEConnectionManager: failed to connect:', err);
            _scheduleReconnect();
        }
    }

    function disconnect() {
        if (_eventSource) {
            _eventSource.close();
            _eventSource = null;
        }
        _isConnected = false;
    }

    return {
        /**
         * Connect to the SSE stream.
         * @param {string} url - SSE endpoint URL.
         * @param {object} callbacks - { onEvent(type, data), onConnect(), onDisconnect() }
         */
        connect(url, callbacks = {}) {
            _onEventCallback = callbacks.onEvent || null;
            _onConnectCallback = callbacks.onConnect || null;
            _onDisconnectCallback = callbacks.onDisconnect || null;
            connect(url);
        },

        disconnect,

        get isConnected() { return _isConnected; }
    };
}());
