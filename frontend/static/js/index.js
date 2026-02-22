/**
 * Ollash Frontend — Vite entry point.
 *
 * This file is the root bundle imported by base.html when USE_VITE_ASSETS=true.
 * It re-exports all core modules so they are bundled together by Vite.
 *
 * Module load order matters:
 *   1. store.js        — global state (no dependencies)
 *   2. theme-manager   — reads/writes store
 *   3. Components      — modal-manager, confirm-dialog, notification-toast
 *   4. Core services   — alert-handler, command-palette, etc.
 *   5. main.js         — initializes everything
 */

// Core foundation
import './core/store.js';
import './core/theme-manager.js';

// Reusable components
import './components/modal-manager.js';
import './components/confirm-dialog.js';
import './components/notification-toast.js';

// Core services
import './core/utils.js';
import './core/alert-handler.js';
import './core/command-palette.js';

// App bootstrap
import './main.js';
