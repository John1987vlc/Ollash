/**
 * Pair Programming Module - Split View Editor
 */
if (typeof window.PairProgrammingModule === 'undefined') {
    window.PairProgrammingModule = (function() {
        let userEditor, agentEditor;

        function init() {
            const userContainer = document.getElementById('monaco-user');
            const agentContainer = document.getElementById('monaco-agent');
            
            if (!userContainer || !agentContainer) {
                console.debug('Pair Programming containers not found, skipping init.');
                return;
            }

            if (typeof monaco !== 'undefined') {
                initEditors(userContainer, agentContainer);
            } else {
                console.warn('Monaco not loaded for Pair Programming');
            }
        }

        function initEditors(userContainer, agentContainer) {
            if (userEditor) return; 

            userEditor = monaco.editor.create(userContainer, {
                value: '# User code here\ndef main():\n    pass',
                language: 'python',
                theme: (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'vs-dark' : 'vs-light',
                automaticLayout: true,
                minimap: { enabled: false }
            });

            agentEditor = monaco.editor.create(agentContainer, {
                value: '# Agent suggestions will appear here\ndef main():\n    print("Hello")',
                language: 'python',
                theme: (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'vs-dark' : 'vs-light',
                readOnly: true,
                automaticLayout: true,
                minimap: { enabled: false }
            });
        }

        window.applyAgentSuggestion = function() {
            if (!agentEditor || !userEditor) return;
            const suggestion = agentEditor.getValue();
            userEditor.setValue(suggestion);
            if (window.showMessage) window.showMessage('Agent code applied', 'success');
        };

        return { init };
    })();

    // Initialize when view is active
    window.loadPairProgramming = window.PairProgrammingModule.init;
}
