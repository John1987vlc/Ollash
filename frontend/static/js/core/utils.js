/**
 * Core Utilities for Ollash Agent
 */

const Utils = {
    escapeHtml: function(unsafe) {
        if (!unsafe) return "";
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    safelySetAttribute: function(element, attr, value) {
        if (element) element.setAttribute(attr, value);
    },

    safelySetTextContent: function(element, value) {
        if (element) element.textContent = value;
    },

    getFileIcon: function(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const iconMap = {
            'html': '🌐', 'css': '🎨', 'js': '⚡',
            'py': '🐍', 'json': '📋', 'md': '📝',
            'txt': '📄', 'jpg': '🖼️', 'png': '🖼️',
            'svg': '🎨', 'xml': '📰', 'yaml': '⚙️', 'yml': '⚙️'
        };
        return iconMap[ext] || '📄';
    },

    getFileExtension: function(filename) {
        const parts = filename.split('.');
        if (parts.length > 1) {
            const ext = parts.pop().toLowerCase();
            const langMap = {
                'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'javascript',
                'py': 'python', 'html': 'html', 'htm': 'html', 'css': 'css', 'scss': 'css',
                'json': 'json', 'xml': 'xml', 'md': 'markdown'
            };
            return langMap[ext] || ext;
        }
        return 'plaintext';
    }
};

// Global shorthand for consistency
window.escapeHtml = Utils.escapeHtml;

// ==================== Document Translator ====================
// Merged from translator.js
document.addEventListener('DOMContentLoaded', () => {
    window.translateCurrentFile = async (targetLang) => {
        const projectName = window.currentProject;
        const filePath = window.currentFile;

        if (!projectName || !filePath) return alert('Select a file first');

        const resp = await fetch('/api/translator/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_name: projectName, file_path: filePath, target_lang: targetLang })
        });

        const data = await resp.json();
        if (data.status === 'success') {
            alert(`File translated to ${targetLang}. Created: ${data.output_file}`);
            if (typeof refreshFileTree === 'function') refreshFileTree();
        } else {
            alert(`Translation failed: ${data.error}`);
        }
    };
});
