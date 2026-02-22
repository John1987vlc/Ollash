/**
 * Sandbox Page Logic - WASM/Docker Playground
 */

(function() {
    let editor;
    const defaultPython = `import sys

def main():
    print("🚀 Hello from the Ollash Secure Sandbox!")
    print(f"Python version: {sys.version}")
    
    # Simple algorithm test
    nums = [i for i in range(10)]
    squares = [x**2 for x in nums]
    print(f"Squares: {squares}")

if __name__ == "__main__":
    main()
`;

    const defaultJS = `console.log("🚀 Hello from Node.js Sandbox!");

// Async test
async function test() {
    const start = Date.now();
    await new Promise(r => setTimeout(r, 100));
    console.log("Async operation complete!");
}

test();
`;

    function initMonaco() {
        if (typeof monaco === 'undefined') {
            console.error('Monaco Editor not found');
            return;
        }

        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.29.1/min/vs' } });
        require(['vs/editor/editor.main'], function() {
            editor = monaco.editor.create(document.getElementById('monaco-editor-container'), {
                value: defaultPython,
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true,
                fontSize: 14,
                fontFamily: 'JetBrains Mono',
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                lineNumbers: 'on',
                roundedSelection: true,
                padding: { top: 16 }
            });
            window.monacoEditorInstance = editor; // Expose for testing
        });
    }

    async function executeCode() {
        const runBtn = document.getElementById('run-sandbox-btn');
        const languageSelect = document.getElementById('language-select');
        const outputContent = document.getElementById('output-content');
        const execTime = document.getElementById('exec-time');

        if (!runBtn) return;

        // Disable button and show loading state IMMEDIATELY
        const originalLabel = runBtn.textContent;
        runBtn.disabled = true;
        runBtn.textContent = 'Ejecutando…';
        runBtn.setAttribute('aria-busy', 'true');

        try {
            // Get code with fallback if editor failed to load
            let code = '';
            if (editor) code = editor.getValue();
            else if (window.monacoEditorInstance) code = window.monacoEditorInstance.getValue();

            const language = languageSelect ? languageSelect.value : 'python';

            if (!code) {
                outputContent.textContent = 'Error: No code to execute (editor might not be loaded)';
                return;
            }

            outputContent.innerHTML = '';
            execTime.textContent = 'Executing...';

            const response = await UIAnimations.withThinkingState('terminal-output', fetch('/sandbox/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, language })
            }));

            const data = await response.json();

            if (data.status === 'success') {
                outputContent.textContent = data.output;
                execTime.textContent = `Completed in ${data.duration.toFixed(3)}s`;
                outputContent.style.color = '#d1d1d1';
            } else {
                outputContent.textContent = `Error: ${data.error}`;
                outputContent.style.color = '#ef4444';
                execTime.textContent = 'Failed';
            }
        } catch (error) {
            console.error('Sandbox execution error:', error);
            outputContent.textContent = `Connection Error: ${error.message}`;
            outputContent.style.color = '#ef4444';
            execTime.textContent = 'Error';
        } finally {
            // Restore button state
            runBtn.disabled = false;
            runBtn.textContent = originalLabel;
            runBtn.removeAttribute('aria-busy');
        }
    }

    // Event Listeners
    document.addEventListener('DOMContentLoaded', () => {
        initMonaco();

        const runBtn = document.getElementById('run-sandbox-btn');
        if (runBtn) runBtn.addEventListener('click', executeCode);
        
        const langSelect = document.getElementById('language-select');
        if (langSelect) {
            langSelect.addEventListener('change', (e) => {
                const lang = e.target.value;
                if (editor) {
                    const model = editor.getModel();
                    monaco.editor.setModelLanguage(model, lang);
                    
                    if (lang === 'python') editor.setValue(defaultPython);
                    else if (lang === 'javascript') editor.setValue(defaultJS);
                }
            });
        }

        const clearBtn = document.getElementById('clear-btn');
        if (clearBtn) {
            clearBtn.onclick = () => {
                document.getElementById('output-content').innerHTML = '// Output cleared...';
                document.getElementById('exec-time').textContent = '';
            };
        }

        const resetBtn = document.getElementById('reset-btn');
        if (resetBtn) {
            resetBtn.onclick = () => {
                if (!editor) return;
                const lang = document.getElementById('language-select').value;
                if (lang === 'python') editor.setValue(defaultPython);
                else if (lang === 'javascript') editor.setValue(defaultJS);
            };
        }
    });
})();
