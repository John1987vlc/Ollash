/**
 * UI Animations & UX Utilities for Ollash Agent
 */

const UIAnimations = {
    thinkingLines: [
        "Analyzing intent...",
        "Scanning project structure...",
        "Generating internal reasoning...",
        "Validating architecture patterns...",
        "Drafting implementation strategy...",
        "Checking for potential regressions...",
        "Optimizing code blocks...",
        "Synchronizing state...",
        "Applying security policies...",
        "Finalizing response..."
    ],

    showThinkingState: function(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        const terminal = document.createElement('div');
        terminal.className = 'thinking-terminal';
        terminal.id = 'thinking-console-' + Date.now();
        
        container.appendChild(terminal);

        let lineIndex = 0;
        const intervalId = setInterval(() => {
            const line = document.createElement('div');
            line.className = 'thinking-line';
            line.textContent = `> ${this.thinkingLines[lineIndex % this.thinkingLines.length]}`;
            terminal.appendChild(line);
            
            // Auto-scroll
            terminal.scrollTop = terminal.scrollHeight;
            
            // Remove old lines if too many
            if (terminal.childNodes.length > 10) {
                terminal.removeChild(terminal.firstChild);
            }
            
            lineIndex++;
        }, 800);

        return {
            id: terminal.id,
            stop: () => {
                clearInterval(intervalId);
                terminal.remove();
            }
        };
    },

    /**
     * Wrap a fetch request with thinking state
     */
    withThinkingState: async function(containerId, fetchPromise) {
        const thinking = this.showThinkingState(containerId);
        try {
            const response = await fetchPromise;
            return response;
        } finally {
            if (thinking) thinking.stop();
        }
    }
};

window.UIAnimations = UIAnimations;
