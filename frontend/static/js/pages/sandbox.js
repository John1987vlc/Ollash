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
        });
    }

    async function executeCode() {
        const code = editor.getValue();
        const language = document.getElementById('language-select').value;
        const outputContent = document.getElementById('output-content');
        const execTime = document.getElementById('exec-time');

        outputContent.innerHTML = '';
        execTime.textContent = 'Executing...';

        try {
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
        }
    }

    // Event Listeners
    document.addEventListener('DOMContentLoaded', () => {
        initMonaco();

        document.getElementById('run-sandbox-btn').addEventListener('click', executeCode);
        
        document.getElementById('language-select').addEventListener('change', (e) => {
            const lang = e.target.value;
            const model = editor.getModel();
            monaco.editor.setModelLanguage(model, lang);
            
            if (lang === 'python') editor.setValue(defaultPython);
            else if (lang === 'javascript') editor.setValue(defaultJS);
        });

        document.getElementById('clear-btn').onclick = () => {
            document.getElementById('output-content').innerHTML = '// Output cleared...';
            document.getElementById('exec-time').textContent = '';
        };

        document.getElementById('reset-btn').onclick = () => {
            const lang = document.getElementById('language-select').value;
            if (lang === 'python') editor.setValue(defaultPython);
            else if (lang === 'javascript') editor.setValue(defaultJS);
        };
    });
})();
