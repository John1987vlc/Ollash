/**
 * ThemeManager — Dynamic dark/light theme switcher.
 *
 * Reads and persists the theme preference in localStorage, applies it via
 * the `data-theme` attribute on <html>, and integrates with OllashStore so
 * other modules can react to theme changes reactively.
 *
 * The CSS variable system in variables.css already defines:
 *   :root            { --color-bg: #0a0a0f; ... }   (dark, default)
 *   [data-theme="light"] { --color-bg: #f5f5f7; ... }
 *
 * Usage:
 *   ThemeManager.init();              // call once on DOMContentLoaded
 *   ThemeManager.toggle();            // flip dark ↔ light
 *   ThemeManager.apply('light');      // set explicitly
 *   ThemeManager.current();           // → 'dark' | 'light'
 *
 * HTML trigger (any element with [data-theme-toggle]):
 *   <button data-theme-toggle aria-label="Toggle theme">...</button>
 */
window.ThemeManager = (function () {
    'use strict';

    const STORAGE_KEY = 'ollash-theme';
    const DEFAULT_THEME = 'dark';
    const VALID_THEMES = new Set(['dark', 'light']);

    /**
     * Return the currently active theme name.
     * @returns {'dark'|'light'}
     */
    function current() {
        const stored = localStorage.getItem(STORAGE_KEY);
        return VALID_THEMES.has(stored) ? stored : DEFAULT_THEME;
    }

    /**
     * Apply the given theme and persist the preference.
     * @param {'dark'|'light'} theme
     */
    function apply(theme) {
        if (!VALID_THEMES.has(theme)) {
            console.warn('[ThemeManager] Unknown theme "' + theme + '", falling back to dark.');
            theme = DEFAULT_THEME;
        }
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);

        // Update store so other modules (e.g. Monaco editor) can react
        if (window.OllashStore) {
            OllashStore.set('theme', theme);
        }

        // Update aria-pressed on all toggle buttons
        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            btn.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
            btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
            
            // Update icon
            const icon = btn.querySelector('#theme-icon');
            if (icon) {
                icon.innerHTML = theme === 'dark' ? '☀️' : '🌙';
            }
        });
    }

    /**
     * Toggle between dark and light themes.
     */
    function toggle() {
        apply(current() === 'dark' ? 'light' : 'dark');
    }

    /**
     * Attach click listeners to all [data-theme-toggle] elements and
     * apply the persisted theme immediately.
     *
     * Safe to call multiple times (idempotent via data-theme-bound attribute).
     */
    function init() {
        // Apply persisted theme before paint to avoid flash of wrong theme
        apply(current());

        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            if (btn.dataset.themeBound) return;  // Already attached
            btn.addEventListener('click', toggle);
            btn.dataset.themeBound = '1';
        });
    }

    return { init, toggle, current, apply };
}());
