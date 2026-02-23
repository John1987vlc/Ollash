/**
 * Sandbox Page Logic - WASM/Docker Playground
 */

(function() {
    window.ollashSandboxEditor = null;
    
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
            console.debug('Monaco not ready, retrying in 500ms...');
            setTimeout(initMonaco, 500);
            return;
        }

        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.29.1/min/vs' } });
        require(['vs/editor/editor.main'], function() {
            window.ollashSandboxEditor = monaco.editor.create(document.getElementById('monaco-editor-container'), {
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
            console.log('🚀 Sandbox Editor initialized');
        });
    }

    async function executeCode() {
        const runBtn = document.getElementById('run-sandbox-btn');
        const languageSelect = document.getElementById('language-select');
        const outputContent = document.getElementById('output-content');
        const execTime = document.getElementById('exec-time');

        if (!runBtn) return;

        try {
            // Get code from global instance
            let code = '';
            if (window.ollashSandboxEditor) {
                code = window.ollashSandboxEditor.getValue();
            }

            if (!code || code.trim().length === 0) {
                outputContent.textContent = 'Error: No code to execute (editor might not be loaded)';
                outputContent.style.color = '#ef4444';
                return;
            }

            // Disable button and show loading state
            const originalLabel = runBtn.innerHTML;
            runBtn.disabled = true;
            runBtn.innerHTML = '<div class="spinner-inline"></div> Executing...';

            const language = languageSelect ? languageSelect.value : 'python';

            outputContent.innerHTML = '';
            execTime.textContent = 'Executing...';

            const response = await fetch('/sandbox/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, language })
            });

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
            
            // Restore button state
            runBtn.disabled = false;
            runBtn.innerHTML = originalLabel;

        } catch (error) {
            console.error('Sandbox execution error:', error);
            outputContent.textContent = `Connection Error: ${error.message}`;
            outputContent.style.color = '#ef4444';
            execTime.textContent = 'Error';
            
            runBtn.disabled = false;
            runBtn.textContent = 'RUN IN SECURE ENVIRONMENT';
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
                if (window.ollashSandboxEditor) {
                    const model = window.ollashSandboxEditor.getModel();
                    monaco.editor.setModelLanguage(model, lang);
                    
                    if (lang === 'python') window.ollashSandboxEditor.setValue(defaultPython);
                    else if (lang === 'javascript') window.ollashSandboxEditor.setValue(defaultJS);
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
                if (!window.ollashSandboxEditor) return;
                const lang = document.getElementById('language-select').value;
                if (lang === 'python') window.ollashSandboxEditor.setValue(defaultPython);
                else if (lang === 'javascript') window.ollashSandboxEditor.setValue(defaultJS);
            };
        }
    });
})();
