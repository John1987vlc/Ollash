/**
 * Ollash Frontend — Vite entry point (TypeScript).
 *
 * This file is the root bundle loaded by base.html when USE_VITE_ASSETS=true.
 * It imports all core modules in dependency order so Vite bundles them together.
 *
 * Module load order:
 *   1. module-registry  — global module registry (no deps)
 *   2. store            — global pub/sub state (no deps)
 *   3. theme-manager    — reads/writes store
 *   4. Components       — modal-manager, confirm-dialog, notification-toast
 *   5. Core services    — utils, ui-animations, sse, alert-handler, etc.
 *   6. main             — bootstraps the SPA after DOMContentLoaded
 *
 * Page-specific scripts ({% block scripts %}) are NOT bundled here;
 * they are still loaded as individual <script> tags by each template.
 */

// ─── Core foundation (TypeScript-migrated) ───────────────────────────────────
import './core/module-registry';
import './core/store';
import './core/theme-manager';
import './core/sse-connection-manager';
import './core/chat-module';

// ─── Reusable UI components ────────────────────────────────────────────────
import './components/modal-manager.js';
import './components/confirm-dialog.js';
import './components/notification-toast.js';
import './components/benchmark-modal.js';

// ─── Core services ─────────────────────────────────────────────────────────
import './core/utils.js';
import './core/ui-animations.js';
import './core/alert-handler.js';
import './core/benchmark-service.js';
import './core/notification-service.js';
import './core/artifact-renderer.js';
import './core/structure-editor.js';
import './core/notifications.js';
import './core/health.js';
import './core/terminal.js';
import './core/command-palette.js';

// ─── App bootstrap ─────────────────────────────────────────────────────────
import './main.js';
