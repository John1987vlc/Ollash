/**
 * Pair Programming Module - Split View Editor
 */
const PairProgrammingModule = (function() {
    let userEditor, agentEditor;

    function init() {
        if (typeof monaco !== 'undefined') {
            initEditors();
        } else {
            console.warn('Monaco not loaded for Pair Programming');
        }
    }

    function initEditors() {
        if (userEditor) return; // Already init

        userEditor = monaco.editor.create(document.getElementById('monaco-user'), {
            value: '# User code here\ndef main():\n    pass',
            language: 'python',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: false }
        });

        agentEditor = monaco.editor.create(document.getElementById('monaco-agent'), {
            value: '# Agent suggestions will appear here\ndef main():\n    print("Hello")',
            language: 'python',
            theme: 'vs-dark',
            readOnly: true,
            automaticLayout: true,
            minimap: { enabled: false }
        });

        // Simulate agent activity
        simulateAgentTyping();
    }

    function simulateAgentTyping() {
        // Mock function to show "ghost cursor" logic later
        setTimeout(() => {
            if(agentEditor) {
                // Flash cursor logic would go here via decorators
            }
        }, 2000);
    }

    window.applyAgentSuggestion = function() {
        const suggestion = agentEditor.getValue();
        userEditor.setValue(suggestion);
        window.showMessage('Agent code applied', 'success');
    };

    return { init };
})();

// Initialize when view is active
window.loadPairProgramming = PairProgrammingModule.init;
