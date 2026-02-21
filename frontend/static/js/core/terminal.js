/**
 * Terminal Module using Xterm.js
 */
window.TerminalModule = (function() {
    let term, fitAddon;
    let currentCommand = '';
    const termPrompt = '\x1b[1;34m$ \x1b[0m';
    
    // DOM Elements
    let terminalContainer, floatingTerminal;

    function init(elements) {
        terminalContainer = elements.terminalContainer;
        floatingTerminal = elements.floatingTerminal;
    }

    function toggle() {
        if (!floatingTerminal) return;
        const isVisible = floatingTerminal.classList.contains('visible');
        if (isVisible) {
            floatingTerminal.classList.remove('visible');
        } else {
            floatingTerminal.classList.add('visible');
            initTerminal();
        }
    }

    function initTerminal() {
        if (term) {
            setTimeout(() => { fitAddon.fit(); term.focus(); }, 100);
            return;
        }
        if (typeof Terminal === 'undefined') return;
        
        term = new Terminal({
            cursorBlink: true,
            theme: { background: '#000000', foreground: '#F8F8F8' },
            fontFamily: 'JetBrains Mono, Fira Code, monospace',
            fontSize: 14
        });
        
        fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        term.open(terminalContainer);
        fitAddon.fit();
        
        term.writeln('\x1b[1;32mOllash Terminal\x1b[0m');
        term.write(termPrompt);

        term.onData(data => {
            if (data === '') {
                term.writeln('');
                if (currentCommand.trim()) executeCommand(currentCommand.trim());
                currentCommand = '';
                term.write(termPrompt);
            } else if (data === '\x7f') {
                if (currentCommand.length > 0) {
                    currentCommand = currentCommand.slice(0, -1);
                    term.write('\b \b');
                }
            } else {
                currentCommand += data;
                term.write(data);
            }
        });
    }

    async function executeCommand(cmd) {
        // Fetch API call to execute terminal command
        term.writeln(`Executing: ${cmd}...`);
        try {
            const resp = await fetch('/api/terminal/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd })
            });
            const data = await resp.json();
            term.writeln(data.output || 'Command completed.');
        } catch (err) {
            term.writeln(`\x1b[1;31mError: ${err.message}\x1b[0m`);
        }
    }

    return {
        init: init,
        toggle: toggle
    };
})();
