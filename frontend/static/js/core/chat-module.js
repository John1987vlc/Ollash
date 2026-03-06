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
                
                // Update header
                const headerName = document.getElementById('chat-header-agent-name');
                const headerIcon = document.getElementById('chat-header-icon');
                if (headerName) headerName.textContent = newAgent.charAt(0).toUpperCase() + newAgent.slice(1);
                if (headerIcon) {
                    const icon = this.querySelector('.agent-card-icon')?.textContent || '🤖';
                    headerIcon.textContent = icon;
                }

                // If switching or re-clicking, start new session
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

        const backBtn = document.getElementById('back-to-welcome-btn');
        if (backBtn) {
            backBtn.onclick = () => {
                resetToWelcome();
            };
        }

        loadHistory();
        console.log("🚀 ChatModule: Initialized with History Support");
    }

    function resetToWelcome() {
        state.currentSessionId = null;
        state.messageCount = 0;
        
        // Restore Welcome UI
        if (state.chatMessages) {
            state.chatMessages.innerHTML = `
                <div class="chat-welcome">
                    <h2>Ollash Agent</h2>
                    <p>Select a specialist or start typing to use the auto-routing orchestrator.</p>
                    <div class="agent-cards">
                        <button class="btn btn-card active" data-agent="orchestrator">
                            <div class="agent-card-icon">🎯</div>
                            <div class="agent-card-title">Orchestrator</div>
                        </button>
                        <button class="btn btn-card" data-agent="code">
                            <div class="agent-card-icon">💻</div>
                            <div class="agent-card-title">Code</div>
                        </button>
                        <button class="btn btn-card" data-agent="network">
                            <div class="agent-card-icon">🌐</div>
                            <div class="agent-card-title">Network</div>
                        </button>
                        <button class="btn btn-card" data-agent="system">
                            <div class="agent-card-icon">⚙️</div>
                            <div class="agent-card-title">System</div>
                        </button>
                        <button class="btn btn-card" data-agent="cybersecurity">
                            <div class="agent-card-icon">🛡️</div>
                            <div class="agent-card-title">Security</div>
                        </button>
                    </div>
                </div>
            `;
            
            // Re-attach listeners to the new agent cards
            state.chatMessages.querySelectorAll('.agent-card').forEach(card => {
                card.onclick = function() {
                    const newAgent = this.dataset.agent;
                    updateHeader(newAgent, this.querySelector('.agent-card-icon')?.textContent);
                    startNewSession(newAgent);
                    
                    state.chatMessages.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
                    this.classList.add('active');
                    state.selectedAgent = newAgent;
                };
            });
        }

        // Update Header to default
        updateHeader('Orchestrator', '🎯');
        loadHistory();
    }

    function updateHeader(name, icon) {
        const headerName = document.getElementById('chat-header-agent-name');
        const headerIcon = document.getElementById('chat-header-icon');
        if (headerName) headerName.textContent = name.charAt(0).toUpperCase() + name.slice(1);
        if (headerIcon) headerIcon.textContent = icon || '🤖';
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
        let thinkingIndicatorId = showThinkingIndicator();
        let currentStatusEl = null;

        source.onmessage = function(event) {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                console.error("Failed to parse SSE data:", event.data);
                return;
            }
            
            // F18: Handle different event types from ChatEventBridge
            const type = data.type;

            if (type === 'token') {
                if (thinkingIndicatorId) {
                    removeThinkingIndicator(thinkingIndicatorId);
                    thinkingIndicatorId = null;
                }
                if (!agentBubble) agentBubble = appendMessage('assistant', '');
                contentBuffer += data.text;
                if (window.formatAnswer) {
                    agentBubble.innerHTML = window.formatAnswer(contentBuffer); // sanitized by formatAnswer
                } else {
                    agentBubble.textContent = contentBuffer; // safe fallback: no HTML injection
                }
                scrollToBottom();
            } 
            else if (type === 'thinking') {
                updateThinkingStatus(data.message);
            }
            else if (type === 'routing') {
                const intent = data.intent;
                const message = data.message;
                window.NotificationToast?.show(message, 'info');
                updateThinkingStatus(message);
                
                // Update header if specialist is selected
                const headerName = document.getElementById('chat-header-agent-name');
                if (headerName && intent !== 'default') {
                    headerName.textContent = intent.charAt(0).toUpperCase() + intent.slice(1);
                }
            }
            else if (type === 'hil_request') {
                const reqId = data.id;
                const action = data.action || data.type; // Support renamed 'action' field or legacy 'type'
                const details = data.details || {};
                
                // Show confirmation bubble in chat
                appendHILConfirmation(reqId, action, details);
            }
            else if (type === 'agent_switch') {
                const agent = data.agent_type;
                const reason = data.reason;
                window.NotificationToast?.show(`Switched to ${agent} specialist`, 'info');
                updateThinkingStatus(`Switching to ${agent} specialist: ${reason}`);
                
                // Update UI active card
                document.querySelectorAll('.agent-card').forEach(c => {
                    c.classList.toggle('active', c.dataset.agent === agent);
                });
                
                // Update header
                const headerName = document.getElementById('chat-header-agent-name');
                if (headerName) headerName.textContent = agent.charAt(0).toUpperCase() + agent.slice(1);
            }
            else if (type === 'tool_start') {
                updateThinkingStatus(`Executing tool: ${data.tool_name}...`);
            }
            else if (type === 'tool_end') {
                const status = data.success ? 'Success' : 'Failed';
                console.log(`Tool ${data.tool_name} finished: ${status}`);
            }
            else if (type === 'final_answer' || type === 'done') {
                source.close();
                if (thinkingIndicatorId) {
                    removeThinkingIndicator(thinkingIndicatorId);
                    thinkingIndicatorId = null;
                }
                
                const finalContent = data.content || contentBuffer;
                if (!agentBubble) {
                    agentBubble = appendMessage('assistant', finalContent);
                } else if (data.content) {
                    if (window.formatAnswer) {
                        const formatted = window.formatAnswer(data.content);
                        if (!formatted && data.content) {
                            agentBubble.textContent = data.content;
                        } else {
                            agentBubble.innerHTML = formatted;
                        }
                    } else {
                        agentBubble.textContent = data.content;
                    }
                }
                
                finalizeResponse(agentBubble, data.metrics);
                loadHistory(); 
            }
            else if (type === 'error') {
                source.close();
                if (thinkingIndicatorId) {
                    removeThinkingIndicator(thinkingIndicatorId);
                    thinkingIndicatorId = null;
                }
                appendMessage('error', `Error: ${data.message}`);
                setLoadingState(false);
            }
            // Feature 6 — Context saturation alert
            else if (type === 'context_saturation_alert') {
                window.NotificationToast?.show(data.warning, 'warning');
            }
            // Feature 4 — Chaos fault injected notification
            else if (type === 'chaos_fault_injected') {
                window.NotificationToast?.show(`[Chaos] ${data.fault_description}`, 'warning');
            }
            // Feature 5 — Live DAG node status update
            else if (type === 'task_status_changed') {
                if (window.DagPanel) window.DagPanel.updateNode(data);
            }
        };

        source.onerror = () => { 
            source.close(); 
            setLoadingState(false); 
            if (thinkingIndicatorId) {
                removeThinkingIndicator(thinkingIndicatorId);
                thinkingIndicatorId = null;
            }
        };

        function updateThinkingStatus(message) {
            const indicator = document.getElementById(thinkingIndicatorId);
            if (indicator) {
                let statusEl = indicator.querySelector('.thinking-status');
                if (!statusEl) {
                    statusEl = document.createElement('div');
                    statusEl.className = 'thinking-status';
                    statusEl.style.fontSize = '0.85em';
                    statusEl.style.color = 'var(--color-text-muted)';
                    statusEl.style.marginTop = '8px';
                    statusEl.style.fontStyle = 'italic';
                    indicator.querySelector('.message-bubble').appendChild(statusEl);
                }
                statusEl.textContent = message;
            }
        }
    }

    function finalizeResponse(bubble, metrics) {
        state.isStreaming = false;
        setLoadingState(false);
        if (metrics && bubble) {
            const mDiv = document.createElement('div');
            mDiv.className = 'message-metrics';
            const duration = metrics.duration || metrics.duration_sec || 0;
            const tokens = metrics.tokens || metrics.total_tokens || 0;
            mDiv.innerHTML = `<span>⏱ ${duration.toFixed(2)}s</span> <span>🪙 ${tokens} tokens</span>`;
            bubble.appendChild(mDiv);
        }
        scrollToBottom();
    }

    function appendMessage(role, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role}-message`;
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        if (role === 'assistant' && window.formatAnswer) {
            const formatted = window.formatAnswer(content);
            // Safety: If formatter returns empty but content exists, fallback to text
            if (!formatted && content) {
                bubble.textContent = content;
            } else {
                bubble.innerHTML = formatted;
            }
        } else {
            bubble.textContent = content;
        }
        
        msgDiv.appendChild(bubble);
        state.chatMessages.appendChild(msgDiv);
        scrollToBottom();
        return bubble;
    }

    function appendHILConfirmation(reqId, action, details) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'chat-message system-message hil-message';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble hil-bubble';
        
        let detailHtml = "";
        if (action === 'run_shell_command') {
            detailHtml = `<code class="hil-code">${details.command}</code>`;
        } else if (action === 'write_file' || action === 'replace') {
            detailHtml = `File: <span class="hil-path">${details.path || details.file_path}</span>`;
        }

        bubble.innerHTML = `
            <div class="hil-header">⚠️ Permission Required</div>
            <div class="hil-action">Agent wants to execute: <strong>${action}</strong></div>
            <div class="hil-details">${detailHtml}</div>
            <div class="hil-buttons">
                <button class="btn btn-error btn-sm" onclick="ChatModule.respondHIL('${reqId}', 'reject')">Reject</button>
                <button class="btn btn-success btn-sm" onclick="ChatModule.respondHIL('${reqId}', 'approve')">Approve</button>
            </div>
        `;
        
        msgDiv.appendChild(bubble);
        state.chatMessages.appendChild(msgDiv);
        scrollToBottom();
    }

    async function respondHIL(requestId, response) {
        // Disable buttons in that bubble
        const buttons = document.querySelectorAll('.hil-buttons button');
        buttons.forEach(b => b.disabled = true);

        try {
            await fetch('/api/hil/respond', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request_id: requestId,
                    response: response,
                    feedback: response === 'reject' ? 'Rejected via chat UI' : ''
                })
            });
            window.NotificationToast?.show(`Action ${response}ed`, 'info');
        } catch (e) {
            window.NotificationToast?.show("Failed to send response", "error");
        }
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

    return { init, sendChatMessage, appendMessage, respondHIL };
})();

window.ChatModule = ChatModule;
