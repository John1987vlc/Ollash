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

export type Theme = 'dark' | 'light';

export interface ThemeManagerAPI {
    init(): void;
    toggle(): void;
    current(): Theme;
    apply(theme: Theme): void;
}

declare global {
    interface Window {
        ThemeManager: ThemeManagerAPI;
        OllashStore?: {
            set(key: string, value: unknown): void;
        };
    }
}

window.ThemeManager = (function (): ThemeManagerAPI {
    'use strict';

    const STORAGE_KEY = 'ollash-theme';
    const DEFAULT_THEME: Theme = 'dark';
    const VALID_THEMES = new Set<string>(['dark', 'light']);

    /**
     * Return the currently active theme name.
     */
    function current(): Theme {
        const stored = localStorage.getItem(STORAGE_KEY);
        return VALID_THEMES.has(stored ?? '') ? (stored as Theme) : DEFAULT_THEME;
    }

    /**
     * Apply the given theme and persist the preference.
     */
    function apply(theme: Theme): void {
        if (!VALID_THEMES.has(theme)) {
            console.warn('[ThemeManager] Unknown theme "' + theme + '", falling back to dark.');
            theme = DEFAULT_THEME;
        }
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);

        // Update store so other modules (e.g. Monaco editor) can react
        if (window.OllashStore) {
            window.OllashStore.set('theme', theme);
        }

        // Update aria-pressed on all toggle buttons
        document.querySelectorAll<HTMLElement>('[data-theme-toggle]').forEach(function (btn) {
            btn.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
            btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');

            // Update icon
            const icon = btn.querySelector<HTMLElement>('#theme-icon');
            if (icon) {
                icon.innerHTML = theme === 'dark' ? '\u2600\ufe0f' : '\ud83c\udf19';
            }
        });
    }

    /**
     * Toggle between dark and light themes.
     */
    function toggle(): void {
        apply(current() === 'dark' ? 'light' : 'dark');
    }

    /**
     * Attach click listeners to all [data-theme-toggle] elements and
     * apply the persisted theme immediately.
     *
     * Safe to call multiple times (idempotent via data-theme-bound attribute).
     */
    function init(): void {
        // Apply persisted theme before paint to avoid flash of wrong theme
        apply(current());

        document.querySelectorAll<HTMLElement>('[data-theme-toggle]').forEach(function (btn) {
            if ((btn as HTMLElement & { dataset: DOMStringMap }).dataset.themeBound) return;
            btn.addEventListener('click', toggle);
            (btn as HTMLElement & { dataset: DOMStringMap }).dataset.themeBound = '1';
        });
    }

    return { init, toggle, current, apply };
}());
