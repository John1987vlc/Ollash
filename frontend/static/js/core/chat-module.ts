/**
 * Ollash - Chat Module
 * Handles sessions, history, and real-time agent communication.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AgentType =
    | 'orchestrator'
    | 'code'
    | 'network'
    | 'system'
    | 'cybersecurity'
    | string;

export type MessageRole = 'user' | 'assistant' | 'error' | 'system';

export interface ChatInitElements {
    chatMessages: HTMLElement;
    chatInput: HTMLInputElement;
    sendBtn: HTMLButtonElement;
}

export interface SessionSummary {
    id: string;
    title: string;
    agent_type: AgentType;
    created_at: string;
}

export interface SessionHistory {
    history: Array<{ role: MessageRole; content: string }>;
}

export interface ChatMetrics {
    duration: number;
    tokens?: number;
}

// Discriminated union for SSE event payloads
type SSEEventPayload =
    | { type: 'token'; text: string }
    | { type: 'thinking'; message: string }
    | { type: 'routing'; intent: string; message: string }
    | { type: 'hil_request'; id: string; details: HILDetails }
    | { type: 'agent_switch'; agent_type: AgentType; reason: string }
    | { type: 'tool_start'; tool_name: string }
    | { type: 'tool_end'; tool_name: string; success: boolean }
    | { type: 'final_answer' | 'done'; content?: string; metrics?: ChatMetrics }
    | { type: 'error'; message: string }
    | { type: 'context_saturation_alert'; warning: string }
    | { type: 'chaos_fault_injected'; fault_description: string }
    | { type: 'task_status_changed'; [key: string]: unknown };

interface HILDetails {
    command?: string;
    path?: string;
    file_path?: string;
    [key: string]: unknown;
}

export interface ChatModuleAPI {
    init(elements: ChatInitElements): void;
    sendChatMessage(message: string): Promise<void>;
    appendMessage(role: MessageRole, content: string): HTMLElement;
    respondHIL(requestId: string, response: 'approve' | 'reject'): Promise<void>;
    deleteSession(sessionId: string): Promise<void>;
    deleteCurrentSession(): Promise<void>;
    deleteAllSessions(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Window augmentations for CDN globals used by this module
// ---------------------------------------------------------------------------
declare global {
    interface Window {
        ChatModule: ChatModuleAPI;
        NotificationToast?: { show(msg: string, type: string): void };
        formatAnswer?: (content: string) => string;
        DagPanel?: { updateNode(data: unknown): void };
    }
}

// ---------------------------------------------------------------------------
// Module implementation
// ---------------------------------------------------------------------------
const ChatModule: ChatModuleAPI = (function (): ChatModuleAPI {

    interface ChatState {
        chatMessages: HTMLElement | null;
        chatInput: HTMLInputElement | null;
        sendBtn: HTMLButtonElement | null;
        historyList: HTMLElement | null;
        currentSessionId: string | null;
        isStreaming: boolean;
        selectedAgent: AgentType;
        messageCount: number;
    }

    const state: ChatState = {
        chatMessages: null,
        chatInput: null,
        sendBtn: null,
        historyList: null,
        currentSessionId: null,
        isStreaming: false,
        selectedAgent: 'orchestrator',
        messageCount: 0,
    };

    function init(elements: ChatInitElements): void {
        state.chatMessages = elements.chatMessages;
        state.chatInput = elements.chatInput;
        state.sendBtn = elements.sendBtn;
        state.historyList = document.getElementById('chat-history-list');

        // Wire history buttons (available regardless of chat input presence)
        const refreshHistoryBtnEarly = document.getElementById('refresh-history-btn');
        if (refreshHistoryBtnEarly) refreshHistoryBtnEarly.onclick = loadHistory;

        const clearAllHistoryBtnEarly = document.getElementById('clear-all-history-btn');
        if (clearAllHistoryBtnEarly) clearAllHistoryBtnEarly.onclick = () => deleteAllSessions();

        if (!state.chatInput || !state.sendBtn) {
            loadHistory();
            return;
        }

        // --- Events ---
        state.sendBtn.onclick = () => {
            const msg = state.chatInput!.value.trim();
            if (msg) sendChatMessage(msg);
        };

        state.chatInput.onkeydown = (e: KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                state.sendBtn!.click();
            }
        };

        // Agent Card Selection -> Starts NEW session
        document.querySelectorAll<HTMLElement>('.agent-card').forEach(card => {
            card.onclick = function (this: HTMLElement) {
                const newAgent = this.dataset.agent as AgentType;

                // Update header
                const headerName = document.getElementById('chat-header-agent-name');
                const headerIcon = document.getElementById('chat-header-icon');
                if (headerName) headerName.textContent = newAgent.charAt(0).toUpperCase() + newAgent.slice(1);
                if (headerIcon) {
                    const icon = this.querySelector<HTMLElement>('.agent-card-icon')?.textContent ?? '\ud83e\udd16';
                    headerIcon.textContent = icon;
                }

                if (state.messageCount > 0 || state.selectedAgent !== newAgent) {
                    startNewSession(newAgent);
                }

                document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                state.selectedAgent = newAgent;
                state.chatInput!.placeholder = `Ask ${newAgent}...`;
            };
        });

        const backBtn = document.getElementById('back-to-welcome-btn');
        if (backBtn) {
            backBtn.onclick = () => resetToWelcome();
        }

        loadHistory();
        console.log('\ud83d\ude80 ChatModule: Initialized with History Support');
    }

    function resetToWelcome(): void {
        state.currentSessionId = null;
        state.messageCount = 0;

        if (state.chatMessages) {
            state.chatMessages.innerHTML = `
                <div class="chat-welcome">
                    <h2>Ollash Agent</h2>
                    <p>Select a specialist or start typing to use the auto-routing orchestrator.</p>
                    <div class="agent-cards">
                        <button class="btn btn-card active" data-agent="orchestrator">
                            <div class="agent-card-icon">\ud83c\udfaf</div>
                            <div class="agent-card-title">Orchestrator</div>
                        </button>
                        <button class="btn btn-card" data-agent="code">
                            <div class="agent-card-icon">\ud83d\udcbb</div>
                            <div class="agent-card-title">Code</div>
                        </button>
                        <button class="btn btn-card" data-agent="network">
                            <div class="agent-card-icon">\ud83c\udf10</div>
                            <div class="agent-card-title">Network</div>
                        </button>
                        <button class="btn btn-card" data-agent="system">
                            <div class="agent-card-icon">\u2699\ufe0f</div>
                            <div class="agent-card-title">System</div>
                        </button>
                        <button class="btn btn-card" data-agent="cybersecurity">
                            <div class="agent-card-icon">\ud83d\udee1\ufe0f</div>
                            <div class="agent-card-title">Security</div>
                        </button>
                    </div>
                </div>
            `;

            // Re-attach listeners to the new agent cards
            state.chatMessages.querySelectorAll<HTMLElement>('.agent-card').forEach(card => {
                card.onclick = function (this: HTMLElement) {
                    const newAgent = this.dataset.agent as AgentType;
                    const icon = this.querySelector<HTMLElement>('.agent-card-icon')?.textContent;
                    updateHeader(newAgent, icon);
                    startNewSession(newAgent);

                    state.chatMessages!.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
                    this.classList.add('active');
                    state.selectedAgent = newAgent;
                };
            });
        }

        updateHeader('Orchestrator', '\ud83c\udfaf');
        loadHistory();
    }

    function updateHeader(name: string, icon?: string | null): void {
        const headerName = document.getElementById('chat-header-agent-name');
        const headerIcon = document.getElementById('chat-header-icon');
        if (headerName) headerName.textContent = name.charAt(0).toUpperCase() + name.slice(1);
        if (headerIcon) headerIcon.textContent = icon ?? '\ud83e\udd16';
    }

    async function startNewSession(agentType: AgentType): Promise<void> {
        state.currentSessionId = null;
        state.messageCount = 0;
        if (state.chatMessages) state.chatMessages.innerHTML = '';

        window.NotificationToast?.show(`Starting new ${agentType} session`, 'info');
        loadHistory();
    }

    async function loadHistory(): Promise<void> {
        if (!state.historyList) return;
        state.historyList.innerHTML = '<div class="history-loading">Loading history...</div>';

        try {
            const resp = await fetch('/api/chat/sessions');
            const data: { sessions: SessionSummary[] } = await resp.json();

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
                    <div class="history-item-body" style="flex:1;min-width:0;cursor:pointer;">
                        <div class="history-item-title">${session.title}</div>
                        <div class="history-item-meta">
                            <span>${session.agent_type}</span>
                            <span>${date}</span>
                        </div>
                    </div>
                    <button class="history-item-delete" title="Delete conversation" style="flex-shrink:0;background:none;border:none;cursor:pointer;color:var(--color-text-muted);font-size:1rem;padding:2px 4px;line-height:1;opacity:0.6;" data-session-id="${session.id}">&#x2715;</button>
                `;
                item.style.display = 'flex';
                item.style.alignItems = 'center';
                item.style.gap = '4px';

                item.querySelector<HTMLElement>('.history-item-body')!.onclick = () => loadSessionHistory(session.id, session.agent_type);
                item.querySelector<HTMLButtonElement>('.history-item-delete')!.onclick = (e: MouseEvent) => {
                    e.stopPropagation();
                    deleteSession(session.id);
                };
                state.historyList!.appendChild(item);
            });
        } catch (_e) {
            state.historyList.innerHTML = '<div class="error-msg">Failed to load history</div>';
        }
    }

    async function loadSessionHistory(sessionId: string, agentType: AgentType): Promise<void> {
        if (state.isStreaming) return;

        try {
            const resp = await fetch(`/api/chat/sessions/${sessionId}/history`);
            const data: SessionHistory = await resp.json();

            state.currentSessionId = sessionId;
            state.selectedAgent = agentType;
            state.messageCount = data.history.length;

            if (state.chatMessages) {
                state.chatMessages.innerHTML = '';
                data.history.forEach(msg => {
                    appendMessage(msg.role, msg.content);
                });
            }

            document.querySelectorAll<HTMLElement>('.agent-card').forEach(c => {
                c.classList.toggle('active', c.dataset.agent === agentType);
            });

            loadHistory();
        } catch (_e) {
            window.NotificationToast?.show('Failed to load conversation', 'error');
        }
    }

    async function sendChatMessage(message: string): Promise<void> {
        if (state.isStreaming || !message) return;

        appendMessage('user', message);
        state.chatInput!.value = '';
        state.messageCount++;

        try {
            setLoadingState(true);

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message,
                    session_id: state.currentSessionId,
                    agent_type: state.selectedAgent,
                }),
            });

            const data: { status: string; session_id: string; message?: string } = await response.json();
            if (data.status === 'started') {
                const isNew = !state.currentSessionId;
                state.currentSessionId = data.session_id;
                connectStream(data.session_id);

                if (isNew) loadHistory();
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            appendMessage('error', `Error: ${(error as Error).message}`);
            setLoadingState(false);
        }
    }

    function connectStream(sessionId: string): void {
        const source = new EventSource(`/api/chat/stream/${sessionId}`);
        let agentBubble: HTMLElement | null = null;
        let contentBuffer = '';
        let thinkingIndicatorId: string | null = showThinkingIndicator();

        source.onmessage = function (event: MessageEvent) {
            let data: SSEEventPayload;
            try {
                data = JSON.parse(event.data) as SSEEventPayload;
            } catch (_e) {
                console.error('Failed to parse SSE data:', event.data);
                return;
            }

            const { type } = data;

            if (type === 'token') {
                if (thinkingIndicatorId) {
                    removeThinkingIndicator(thinkingIndicatorId);
                    thinkingIndicatorId = null;
                }
                if (!agentBubble) agentBubble = appendMessage('assistant', '');
                contentBuffer += data.text;
                if (window.formatAnswer) {
                    agentBubble.innerHTML = window.formatAnswer(contentBuffer);
                } else {
                    agentBubble.textContent = contentBuffer;
                }
                scrollToBottom();
            } else if (type === 'thinking') {
                updateThinkingStatus(thinkingIndicatorId, data.message);
            } else if (type === 'routing') {
                window.NotificationToast?.show(data.message, 'info');
                updateThinkingStatus(thinkingIndicatorId, data.message);

                const headerName = document.getElementById('chat-header-agent-name');
                if (headerName && data.intent !== 'default') {
                    headerName.textContent = data.intent.charAt(0).toUpperCase() + data.intent.slice(1);
                }
            } else if (type === 'hil_request') {
                appendHILConfirmation(data.id, type, data.details);
            } else if (type === 'agent_switch') {
                window.NotificationToast?.show(`Switched to ${data.agent_type} specialist`, 'info');
                updateThinkingStatus(thinkingIndicatorId, `Switching to ${data.agent_type} specialist: ${data.reason}`);

                document.querySelectorAll<HTMLElement>('.agent-card').forEach(c => {
                    c.classList.toggle('active', c.dataset.agent === data.agent_type);
                });

                const headerName = document.getElementById('chat-header-agent-name');
                if (headerName) headerName.textContent = data.agent_type.charAt(0).toUpperCase() + data.agent_type.slice(1);
            } else if (type === 'tool_start') {
                updateThinkingStatus(thinkingIndicatorId, `Executing tool: ${data.tool_name}...`);
            } else if (type === 'tool_end') {
                const status = data.success ? 'Success' : 'Failed';
                console.log(`Tool ${data.tool_name} finished: ${status}`);
            } else if (type === 'final_answer' || type === 'done') {
                source.close();
                if (thinkingIndicatorId) {
                    removeThinkingIndicator(thinkingIndicatorId);
                    thinkingIndicatorId = null;
                }

                const finalContent = data.content ?? contentBuffer;
                if (!agentBubble) {
                    agentBubble = appendMessage('assistant', finalContent);
                } else if (data.content) {
                    if (window.formatAnswer) {
                        agentBubble.innerHTML = window.formatAnswer(data.content);
                    } else {
                        agentBubble.textContent = data.content;
                    }
                }

                finalizeResponse(agentBubble, data.metrics);
                loadHistory();
            } else if (type === 'error') {
                source.close();
                if (thinkingIndicatorId) {
                    removeThinkingIndicator(thinkingIndicatorId);
                    thinkingIndicatorId = null;
                }
                appendMessage('error', `Error: ${data.message}`);
                setLoadingState(false);
            } else if (type === 'context_saturation_alert') {
                window.NotificationToast?.show(data.warning, 'warning');
            } else if (type === 'chaos_fault_injected') {
                window.NotificationToast?.show(`[Chaos] ${data.fault_description}`, 'warning');
            } else if (type === 'task_status_changed') {
                window.DagPanel?.updateNode(data);
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
    }

    function updateThinkingStatus(indicatorId: string | null, message: string): void {
        if (!indicatorId) return;
        const indicator = document.getElementById(indicatorId);
        if (indicator) {
            let statusEl = indicator.querySelector<HTMLElement>('.thinking-status');
            if (!statusEl) {
                statusEl = document.createElement('div');
                statusEl.className = 'thinking-status';
                statusEl.style.fontSize = '0.85em';
                statusEl.style.color = 'var(--color-text-muted)';
                statusEl.style.marginTop = '8px';
                statusEl.style.fontStyle = 'italic';
                indicator.querySelector('.message-bubble')?.appendChild(statusEl);
            }
            statusEl.textContent = message;
        }
    }

    function finalizeResponse(bubble: HTMLElement | null, metrics?: ChatMetrics): void {
        state.isStreaming = false;
        setLoadingState(false);
        if (metrics && bubble) {
            const mDiv = document.createElement('div');
            mDiv.className = 'message-metrics';
            mDiv.innerHTML = `<span>\u23f1 ${metrics.duration.toFixed(2)}s</span> <span>\ud83e\ude99 ${metrics.tokens ?? 0} tokens</span>`;
            bubble.appendChild(mDiv);
        }
        scrollToBottom();
    }

    function appendMessage(role: MessageRole, content: string): HTMLElement {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role}-message`;
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = (role === 'assistant' && window.formatAnswer) ? window.formatAnswer(content) : content;
        msgDiv.appendChild(bubble);
        state.chatMessages!.appendChild(msgDiv);
        scrollToBottom();
        return bubble;
    }

    function appendHILConfirmation(reqId: string, _action: string, details: HILDetails): void {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'chat-message system-message hil-message';

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble hil-bubble';

        let detailHtml = '';
        if (_action === 'run_shell_command') {
            detailHtml = `<code class="hil-code">${details.command ?? ''}</code>`;
        } else if (_action === 'write_file' || _action === 'replace') {
            detailHtml = `File: <span class="hil-path">${details.path ?? details.file_path ?? ''}</span>`;
        }

        bubble.innerHTML = `
            <div class="hil-header">\u26a0\ufe0f Permission Required</div>
            <div class="hil-action">Agent wants to execute: <strong>${_action}</strong></div>
            <div class="hil-details">${detailHtml}</div>
            <div class="hil-buttons">
                <button class="btn btn-error btn-sm" onclick="ChatModule.respondHIL('${reqId}', 'reject')">Reject</button>
                <button class="btn btn-success btn-sm" onclick="ChatModule.respondHIL('${reqId}', 'approve')">Approve</button>
            </div>
        `;

        msgDiv.appendChild(bubble);
        state.chatMessages!.appendChild(msgDiv);
        scrollToBottom();
    }

    async function respondHIL(requestId: string, response: 'approve' | 'reject'): Promise<void> {
        document.querySelectorAll<HTMLButtonElement>('.hil-buttons button').forEach(b => { b.disabled = true; });

        try {
            await fetch('/api/hil/respond', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request_id: requestId,
                    response,
                    feedback: response === 'reject' ? 'Rejected via chat UI' : '',
                }),
            });
            window.NotificationToast?.show(`Action ${response}ed`, 'info');
        } catch (_e) {
            window.NotificationToast?.show('Failed to send response', 'error');
        }
    }

    function showThinkingIndicator(): string {
        const id = 'thinking-' + Date.now();
        const div = document.createElement('div');
        div.id = id;
        div.className = 'chat-message assistant-message';
        div.innerHTML = `<div class="message-bubble thinking-indicator"><div class="dot-pulse"></div><div class="dot-pulse" style="animation-delay:0.2s"></div><div class="dot-pulse" style="animation-delay:0.4s"></div></div>`;
        state.chatMessages!.appendChild(div);
        scrollToBottom();
        return id;
    }

    function removeThinkingIndicator(id: string): void {
        document.getElementById(id)?.remove();
    }

    function setLoadingState(loading: boolean): void {
        state.isStreaming = loading;
        if (state.sendBtn) state.sendBtn.disabled = loading;
    }

    function scrollToBottom(): void {
        if (state.chatMessages) state.chatMessages.scrollTop = state.chatMessages.scrollHeight;
    }

    async function deleteSession(sessionId: string): Promise<void> {
        if (!sessionId) {
            resetToWelcome();
            return;
        }
        try {
            await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
            if (sessionId === state.currentSessionId) {
                resetToWelcome();
            } else {
                loadHistory();
            }
            window.NotificationToast?.show('Conversation deleted', 'info');
        } catch (_e) {
            window.NotificationToast?.show('Failed to delete conversation', 'error');
        }
    }

    async function deleteCurrentSession(): Promise<void> {
        const sessionId = state.currentSessionId;
        if (!sessionId) {
            resetToWelcome();
            return;
        }
        await deleteSession(sessionId);
    }

    async function deleteAllSessions(): Promise<void> {
        const confirmed = window.ConfirmDialog
            ? await window.ConfirmDialog.ask('Delete all conversations? This cannot be undone.')
            : confirm('Delete all conversations? This cannot be undone.');
        if (!confirmed) return;

        try {
            await fetch('/api/chat/sessions', { method: 'DELETE' });
            resetToWelcome();
            window.NotificationToast?.show('All conversations deleted', 'info');
        } catch (_e) {
            window.NotificationToast?.show('Failed to delete all conversations', 'error');
        }
    }

    return { init, sendChatMessage, appendMessage, respondHIL, deleteSession, deleteCurrentSession, deleteAllSessions };
})();

window.ChatModule = ChatModule;
