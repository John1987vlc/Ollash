/**
 * Ollash - Chat Module
 * Handles sessions, history, and real-time agent communication.
 */
const ChatModule = (function() {
    let state = {
        chatMessages: null,
        chatInput: null,
        sendBtn: null,
        historyList: null,
        currentSessionId: null,
        isStreaming: false,
        selectedAgent: 'orchestrator',
        messageCount: 0 // Used to track if session should be saved
    };

    function init(elements) {
        state.chatMessages = elements.chatMessages;
        state.chatInput = elements.chatInput;
        state.sendBtn = elements.sendBtn;
        state.historyList = document.getElementById('chat-history-list');

        if (!state.chatInput || !state.sendBtn) return;

        // --- Events ---
        state.sendBtn.onclick = () => {
            const msg = state.chatInput.value.trim();
            if (msg) sendChatMessage(msg);
        };

        state.chatInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                state.sendBtn.click();
            }
        };

        // Agent Card Selection -> Starts NEW session
        document.querySelectorAll('.agent-card').forEach(card => {
            card.onclick = function() {
                const newAgent = this.dataset.agent;
                
                // If switching or re-clicking, start new session
                // Unless we are already in an empty session of the same type
                if (state.messageCount > 0 || state.selectedAgent !== newAgent) {
                    startNewSession(newAgent);
                }

                document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                state.selectedAgent = newAgent;
                state.chatInput.placeholder = `Ask ${newAgent}...`;
            };
        });

        const refreshHistoryBtn = document.getElementById('refresh-history-btn');
        if (refreshHistoryBtn) refreshHistoryBtn.onclick = loadHistory;

        loadHistory();
        console.log("🚀 ChatModule: Initialized with History Support");
    }

    async function startNewSession(agentType) {
        state.currentSessionId = null;
        state.messageCount = 0;
        if (state.chatMessages) state.chatMessages.innerHTML = '';
        
        // Visual feedback
        window.NotificationToast?.show(`Starting new ${agentType} session`, 'info');
        
        // Refresh history to hide empty previous session if any
        loadHistory();
    }

    async function loadHistory() {
        if (!state.historyList) return;
        state.historyList.innerHTML = '<div class="history-loading">Loading history...</div>';

        try {
            const resp = await fetch('/api/chat/sessions');
            const data = await resp.json();

            if (data.sessions.length === 0) {
                state.historyList.innerHTML = '<div class="history-empty">No past sessions.</div>';
                return;
            }

            state.historyList.innerHTML = '';
            data.sessions.forEach(session => {
                const item = document.createElement('div');
                item.className = 'history-item';
                if (session.id === state.currentSessionId) item.classList.add('active');
                
                const date = new Date(session.created_at).toLocaleDateString();
                item.innerHTML = `
                    <div class="history-item-title">${session.title}</div>
                    <div class="history-item-meta">
                        <span>${session.agent_type}</span>
                        <span>${date}</span>
                    </div>
                `;
                
                item.onclick = () => loadSessionHistory(session.id, session.agent_type);
                state.historyList.appendChild(item);
            });
        } catch (e) {
            state.historyList.innerHTML = '<div class="error-msg">Failed to load history</div>';
        }
    }

    async function loadSessionHistory(sessionId, agentType) {
        if (state.isStreaming) return;
        
        try {
            const resp = await fetch(`/api/chat/sessions/${sessionId}`);
            const data = await resp.json();

            state.currentSessionId = sessionId;
            state.selectedAgent = agentType;
            state.messageCount = data.history.length;
            
            // UI Update
            if (state.chatMessages) {
                state.chatMessages.innerHTML = '';
                data.history.forEach(msg => {
                    appendMessage(msg.role, msg.content);
                });
            }

            // Highlight in sidebar
            document.querySelectorAll('.agent-card').forEach(c => {
                c.classList.toggle('active', c.dataset.agent === agentType);
            });

            // Highlight in history
            document.querySelectorAll('.history-item').forEach(item => {
                item.classList.remove('active');
            });

            loadHistory(); // Re-render to update active state
        } catch (e) {
            window.NotificationToast?.show("Failed to load conversation", "error");
        }
    }

    async function sendChatMessage(message) {
        if (state.isStreaming || !message) return;

        appendMessage('user', message);
        state.chatInput.value = '';
        state.messageCount++;

        try {
            setLoadingState(true);

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: state.currentSessionId,
                    agent_type: state.selectedAgent
                })
            });

            const data = await response.json();
            if (data.status === 'started') {
                const isNew = !state.currentSessionId;
                state.currentSessionId = data.session_id;
                connectStream(data.session_id);
                
                if (isNew) loadHistory(); // Refresh list to show new session
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            appendMessage('error', `Error: ${error.message}`);
            setLoadingState(false);
        }
    }

    function connectStream(sessionId) {
        const source = new EventSource(`/api/chat/stream/${sessionId}`);
        let agentBubble = null;
        let contentBuffer = "";
        const thinkingId = showThinkingIndicator();

        source.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.event === 'token') {
                removeThinkingIndicator(thinkingId);
                if (!agentBubble) agentBubble = appendMessage('assistant', '');
                contentBuffer += data.text;
                agentBubble.innerHTML = window.formatAnswer ? window.formatAnswer(contentBuffer) : contentBuffer;
                scrollToBottom();
            } 
            else if (data.event === 'done') {
                source.close();
                finalizeResponse(agentBubble, data.metrics);
                loadHistory(); // Refresh to update title if it was first message
            }
            else if (data.event === 'error') {
                source.close();
                appendMessage('error', `Error: ${data.message}`);
                setLoadingState(false);
            }
        };

        source.onerror = () => { source.close(); setLoadingState(false); };
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

    function appendMessage(role, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role}-message`;
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = (role === 'assistant' && window.formatAnswer) ? window.formatAnswer(content) : content;
        msgDiv.appendChild(bubble);
        state.chatMessages.appendChild(msgDiv);
        scrollToBottom();
        return bubble;
    }

    function showThinkingIndicator() {
        const id = 'thinking-' + Date.now();
        const div = document.createElement('div');
        div.id = id; div.className = 'chat-message assistant-message';
        div.innerHTML = `<div class="message-bubble thinking-indicator"><div class="dot-pulse"></div><div class="dot-pulse" style="animation-delay:0.2s"></div><div class="dot-pulse" style="animation-delay:0.4s"></div></div>`;
        state.chatMessages.appendChild(div);
        scrollToBottom();
        return id;
    }

    function removeThinkingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function setLoadingState(loading) {
        state.isStreaming = loading;
        if (state.sendBtn) state.sendBtn.disabled = loading;
    }

    function scrollToBottom() {
        if (state.chatMessages) state.chatMessages.scrollTop = state.chatMessages.scrollHeight;
    }

    return { init, sendChatMessage, appendMessage };
})();

window.ChatModule = ChatModule;
