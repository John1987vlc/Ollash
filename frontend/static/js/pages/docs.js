/**
 * Ollash Documentation Viewer Module
 * Manages dynamic documentation tree and content rendering.
 */
window.DocsModule = (function() {
    let docsNav, docsContent;

    function init() {
        docsNav = document.getElementById('docs-nav');
        docsContent = document.getElementById('docs-content');
        
        if (!docsNav || !docsContent) {
            console.debug("DocsModule elements missing (expected if not in docs view)");
            return;
        }

        // Configure marked options
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                highlight: function(code, lang) {
                    if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return code;
                },
                headerIds: true,
                gfm: true,
                breaks: true
            });
        }

        loadDocsTree();
        console.log("🚀 DocsModule initialized");
    }

    /**
     * Loads the documentation tree from the API.
     */
    async function loadDocsTree() {
        if (!docsNav) return;
        try {
            const response = await fetch('/api/docs/tree');
            const tree = await response.json();
            renderDocsTree(tree);
            
            // Auto-load README.md if available
            const readme = tree.find(item => item.name === 'README.md');
            if (readme) {
                loadDocContent(readme.path, 'README.md');
            }
        } catch (error) {
            console.error('Error loading docs tree:', error);
            docsNav.innerHTML = `<div class="error-msg">Failed to load documentation tree.</div>`;
        }
    }

    /**
     * Renders the documentation tree in the sidebar.
     */
    function renderDocsTree(tree) {
        if (!docsNav) return;
        docsNav.innerHTML = '';
        
        tree.forEach(item => {
            if (item.type === 'file') {
                const btn = createNavItem(item.name, item.path);
                docsNav.appendChild(btn);
            } else if (item.type === 'directory') {
                const folderDiv = document.createElement('div');
                folderDiv.className = 'docs-nav-folder';
                
                const label = document.createElement('div');
                label.className = 'docs-nav-folder-label';
                label.textContent = item.name;
                folderDiv.appendChild(label);
                
                const content = document.createElement('div');
                content.className = 'docs-nav-folder-content';
                
                if (item.children) {
                    item.children.forEach(child => {
                        content.appendChild(createNavItem(child.name, child.path));
                    });
                }
                
                folderDiv.appendChild(content);
                docsNav.appendChild(folderDiv);
            }
        });
    }

    /**
     * Creates a navigation item button.
     */
    function createNavItem(name, path) {
        const btn = document.createElement('button');
        btn.className = 'docs-nav-item';
        btn.dataset.path = path;
        
        const icon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`;
        btn.innerHTML = `${icon} ${name}`;
        
        btn.onclick = () => {
            // Remove active class from all items
            document.querySelectorAll('.docs-nav-item').forEach(i => i.classList.remove('active'));
            btn.classList.add('active');
            loadDocContent(path, name);
        };
        
        return btn;
    }

    /**
     * Loads and renders the content of a document.
     */
    async function loadDocContent(path, name) {
        if (!docsContent) return;
        docsContent.innerHTML = `<div class="loading-spinner"></div><p>Loading ${name}...</p>`;
        
        try {
            const response = await fetch(`/api/docs/content/${encodeURIComponent(path)}`);
            const data = await response.json();
            
            if (data.error) {
                docsContent.innerHTML = `<div class="error-msg">Error: ${data.error}</div>`;
                return;
            }
            
            if (typeof marked !== 'undefined') {
                docsContent.innerHTML = marked.parse(data.content);
                // Re-initialize highlight.js for the new content
                if (typeof hljs !== 'undefined') {
                    docsContent.querySelectorAll('pre code').forEach((block) => {
                        hljs.highlightElement(block);
                    });
                }
            } else {
                docsContent.innerHTML = `<pre>${data.content}</pre>`;
            }
            
            // Scroll to top
            const mainEl = document.querySelector('.docs-main');
            if (mainEl) mainEl.scrollTop = 0;
            
        } catch (error) {
            console.error('Error loading doc content:', error);
            docsContent.innerHTML = `<div class="error-msg">Failed to load content for ${name}.</div>`;
        }
    }

    return {
        init: init,
        loadDocs: loadDocsTree
    };
})();
