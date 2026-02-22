// Prompt Studio with Validator

const PromptStudio = {
    init: function() {
        this.input = document.getElementById('prompt-editor');
        this.output = document.getElementById('validation-output');
        this.debounceTimer = null;
        
        if(this.input) {
            this.input.addEventListener('input', () => this.handleInput());
        }
    },
    
    handleInput: function() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.validate(), 800);
    },
    
    validate: async function() {
        const text = this.input.value;
        if (!text) {
            this.output.innerHTML = '';
            return;
        }
        
        try {
            const res = await fetch('/prompts/api/validate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ prompt: text })
            });
            const data = await res.json();
            this.renderWarnings(data.warnings);
        } catch (e) {
            console.error(e);
        }
    },
    
    renderWarnings: function(warnings) {
        this.output.innerHTML = '';
        if (warnings.length === 0) {
            this.output.innerHTML = '<div class="alert-success">✓ Prompt looks good!</div>';
            return;
        }
        
        warnings.forEach(w => {
            const div = document.createElement('div');
            div.className = `alert-item ${w.severity}`;
            div.style.padding = '8px';
            div.style.marginTop = '5px';
            div.style.borderRadius = '4px';
            
            if (w.severity === 'critical') {
                div.style.background = 'rgba(239, 68, 68, 0.2)';
                div.style.color = '#ef4444';
            } else if (w.severity === 'warning') {
                div.style.background = 'rgba(245, 158, 11, 0.2)';
                div.style.color = '#f59e0b';
            } else {
                div.style.background = 'rgba(99, 102, 241, 0.1)';
                div.style.color = '#6366f1';
            }
            
            div.textContent = `⚠️ ${w.message}`;
            this.output.appendChild(div);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => PromptStudio.init());
