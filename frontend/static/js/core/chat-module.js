/**
 * Ollash - Chat Module (Reconstructed)
 * Handles the interaction loop between the user and the AI Agent via SSE.
 */

const ChatModule = (function() {
    let state = {
        chatMessages: null,
        chatInput: null,
        sendBtn: null,
        currentSessionId: null,
        isStreaming: false,
        selectedAgent: 'orchestrator'
    };

    /**
     * Initializes the chat interface and event listeners.
     */
    function init(elements) {
        state.chatMessages = elements.chatMessages;
        state.chatInput = elements.chatInput;
        state.sendBtn = elements.sendBtn;

        if (!state.chatInput || !state.sendBtn) {
            console.warn("ChatModule: Required DOM elements missing during init.");
            return;
        }

        // Event: Click Send
        state.sendBtn.addEventListener('click', () => {
            const msg = state.chatInput.value.trim();
            if (msg) sendChatMessage(msg);
        });

        // Event: Enter to Send
        state.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                state.sendBtn.click();
            }
        });

        // Event: Agent Card Selection
        document.querySelectorAll('.agent-card').forEach(card => {
            card.addEventListener('click', function() {
                document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                state.selectedAgent = this.dataset.agent;
                state.chatInput.placeholder = `Ask ${state.selectedAgent.charAt(0).toUpperCase() + state.selectedAgent.slice(1)}...`;
                state.chatInput.focus();
            });
        });

        console.log("🚀 ChatModule: Initialized successfully");
    }

    /**
     * Core function to send a message and handle the lifecycle.
     */
    async function sendChatMessage(message, agentOverride = null) {
        if (state.isStreaming || !message) return;

        const agentType = agentOverride || state.selectedAgent;

        // 1. UI Update: Add user bubble
        appendMessage('user', message);
        state.chatInput.value = '';
        state.chatInput.style.height = 'auto';

        try {
            setLoadingState(true);

            // 2. Request backend to process instruction
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: state.currentSessionId,
                    agent_type: agentType
                })
            });

            const data = await response.json();
            if (data.status === 'started') {
                state.currentSessionId = data.session_id;
                // 3. Connect to SSE for the streamed response
                connectStream(data.session_id);
            } else {
                throw new Error(data.message || 'Server rejected the message');
            }

        } catch (error) {
            console.error("ChatModule Error:", error);
            appendMessage('error', `System Error: ${error.message}`);
            setLoadingState(false);
        }
    }

    /**
     * Handles the SSE connection for real-time text.
     */
    function connectStream(sessionId) {
        const source = new EventSource(`/api/chat/stream/${sessionId}`);
        let agentBubble = null;
        let contentBuffer = "";

        source.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.event === 'token') {
                if (!agentBubble) {
                    agentBubble = appendMessage('assistant', '');
                }
                contentBuffer += data.text;
                
                // Use global formatAnswer if available
                if (window.formatAnswer) {
                    agentBubble.innerHTML = window.formatAnswer(contentBuffer);
                } else {
                    agentBubble.textContent = contentBuffer;
                }
                scrollToBottom();
            } 
            else if (data.event === 'done') {
                source.close();
                finalizeResponse(agentBubble, data.metrics);
            }
            else if (data.event === 'error') {
                source.close();
                appendMessage('error', `Stream Error: ${data.message}`);
                setLoadingState(false);
            }
        };

        source.onerror = function() {
            source.close();
            setLoadingState(false);
        };
    }

    function finalizeResponse(bubble, metrics) {
        state.isStreaming = false;
        setLoadingState(false);
        
        if (metrics && bubble) {
            const mDiv = document.createElement('div');
            mDiv.className = 'message-metrics';
            mDiv.innerHTML = `<span>⏱ ${metrics.duration.toFixed(2)}s</span> <span>🪙 ${metrics.tokens || 0} tokens</span>`;
            bubble.appendChild(mDiv);
        }
        scrollToBottom();
    }

    /**
     * Appends a new message to the chat container.
     */
    function appendMessage(role, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role}-message`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        if (role === 'user') {
            bubble.textContent = content;
        } else if (role === 'error') {
            bubble.className += ' error-bubble';
            bubble.textContent = content;
        } else {
            // Assistant content starts empty for streaming
            bubble.textContent = content;
        }

        msgDiv.appendChild(bubble);
        state.chatMessages.appendChild(msgDiv);
        scrollToBottom();
        return bubble;
    }

    function setLoadingState(loading) {
        state.isStreaming = loading;
        if (state.sendBtn) {
            state.sendBtn.disabled = loading;
            state.sendBtn.classList.toggle('loading', loading);
        }
    }

    function scrollToBottom() {
        if (state.chatMessages) {
            state.chatMessages.scrollTop = state.chatMessages.scrollHeight;
        }
    }

    // Public API
    return {
        init,
        sendChatMessage,
        appendMessage
    };
})();

// Export to window for main.js and E2E tests
window.ChatModule = ChatModule;
