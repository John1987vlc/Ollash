/**
 * Ollash Command Palette & Breadcrumbs
 * Provides quick navigation and context awareness.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Navigation Routes for Palette
    const routes = [
        { title: 'Chat / Agent', path: '/chat', view: 'chat', icon: 'M4 4H16V13H7L4 16V4Z' },
        { title: 'New Project', path: '/create', view: 'create', icon: 'M10 4V16M4 10H16' },
        { title: 'Projects Explorer', path: '/projects', view: 'projects', icon: 'M3 4H17V16H3V4Z M7 8H13 M7 12H13' },
        { title: 'System Architecture', path: '/architecture', view: 'architecture', icon: 'M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5' },
        { title: 'Documentation', path: '/docs', view: 'docs', icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z' },
        { title: 'Cybersecurity Scanner', path: '/security', view: 'security', icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
        { title: 'Model Benchmark', path: '/benchmark', view: 'benchmark', icon: 'M3 12h3v6H3z M8.5 7h3v11h-3z M14 2h3v16h-3z' },
        { title: 'Automations & Triggers', path: '/automations', view: 'automations', icon: 'M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0 M10 6v4l3 3' },
        { title: 'Knowledge Base (Brain)', path: '/knowledge', view: 'knowledge', icon: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z' },
        { title: 'Settings & Config', path: '/settings', view: 'settings', icon: 'M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0 M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z' },
    ];

    // 2. DOM Elements
    const paletteOverlay = document.getElementById('command-palette-overlay');
    const paletteInput = document.getElementById('command-palette-input');
    const paletteResults = document.getElementById('command-palette-results');
    const breadcrumbsContainer = document.getElementById('breadcrumbs-container');

    let selectedIndex = 0;
    let filteredRoutes = [...routes];

    // 3. Functions
    function showPalette() {
        paletteOverlay.classList.add('active');
        paletteInput.value = '';
        renderResults();
        paletteInput.focus();
    }

    function hidePalette() {
        paletteOverlay.classList.remove('active');
        // Return focus to the element that triggered the palette
        if (document.activeElement === paletteInput) {
            paletteInput.blur();
        }
    }

    /**
     * Focus trap: cycles focus between the input and result items while palette is open.
     */
    function trapFocus(e) {
        if (!paletteOverlay.classList.contains('active')) return;
        if (e.key !== 'Tab') return;

        const focusable = [paletteInput, ...paletteResults.querySelectorAll('.command-result-item')];
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
            if (document.activeElement === first) {
                e.preventDefault();
                last.focus();
            }
        } else {
            if (document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    }

    function renderResults() {
        paletteResults.innerHTML = '';
        const query = paletteInput.value.toLowerCase();
        filteredRoutes = routes.filter(r => r.title.toLowerCase().includes(query));

        if (filteredRoutes.length === 0) {
            paletteResults.innerHTML = '<div class="command-result-item">No results found</div>';
            return;
        }

        filteredRoutes.forEach((route, index) => {
            const item = document.createElement('div');
            item.className = `command-result-item ${index === selectedIndex ? 'selected' : ''}`;
            item.setAttribute('tabindex', '0');
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', index === selectedIndex ? 'true' : 'false');
            item.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
                    <path d="${route.icon}"></path>
                </svg>
                <div class="command-result-info">
                    <span class="command-result-title">${route.title}</span>
                    <span class="command-result-path">${route.path}</span>
                </div>
            `;
            item.onclick = () => navigateTo(route);
            item.onkeydown = (e) => { if (e.key === 'Enter') navigateTo(route); };
            paletteResults.appendChild(item);
        });
    }

    function navigateTo(route) {
        hidePalette();
        // Since it's a multi-page app with Flask but uses views internally for some JS logic,
        // we'll check if we should just change window.location
        window.location.href = route.path;
    }

    function updateBreadcrumbs() {
        if (!breadcrumbsContainer) return;
        
        const path = window.location.pathname;
        const segments = path.split('/').filter(s => s);
        
        let html = `
            <div class="breadcrumb-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
                <span>Ollash</span>
            </div>
        `;

        if (segments.length > 0) {
            segments.forEach((segment, index) => {
                const title = segment.charAt(0).toUpperCase() + segment.slice(1);
                const isActive = index === segments.length - 1;
                html += `
                    <div class="breadcrumb-separator">/</div>
                    <div class="breadcrumb-item ${isActive ? 'active' : ''}">
                        <span>${title}</span>
                    </div>
                `;
            });
        } else {
            html += `
                <div class="breadcrumb-separator">/</div>
                <div class="breadcrumb-item active">
                    <span>Chat</span>
                </div>
            `;
        }
        
        breadcrumbsContainer.innerHTML = html;
    }

    // 4. Event Listeners
    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            showPalette();
        }
        if (e.key === 'Escape' && paletteOverlay.classList.contains('active')) {
            hidePalette();
        }
        trapFocus(e);
    });

    paletteOverlay.onclick = (e) => {
        if (e.target === paletteOverlay) hidePalette();
    };

    paletteInput.oninput = () => {
        selectedIndex = 0;
        renderResults();
    };

    paletteInput.onkeydown = (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % filteredRoutes.length;
            renderResults();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + filteredRoutes.length) % filteredRoutes.length;
            renderResults();
        } else if (e.key === 'Enter') {
            if (filteredRoutes[selectedIndex]) {
                navigateTo(filteredRoutes[selectedIndex]);
            }
        }
    };

    // 5. Initial Execution
    updateBreadcrumbs();
});
