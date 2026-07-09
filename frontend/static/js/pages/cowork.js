/**
 * CoWork module — folder-aware document Q&A chat.
 *
 * Responsibilities:
 *   - Folder picker (assigns a local path as workspace)
 *   - File browser (lists workspace files via GET /api/cowork/files)
 *   - Chat interface (reuses /api/chat SSE infrastructure with mode=cowork)
 *   - Remembers last workspace in localStorage
 */
'use strict';

window.CoworkModule = (function () {
  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  let _sessionId = null;
  let _workspacePath = null;
  let _eventSource = null;
  let _isThinking = false;
  let _initialized = false;

  const LS_KEY_PATH = 'cowork_last_path';
  const LS_KEY_SESSION = 'cowork_session_id';

  // -------------------------------------------------------------------------
  // DOM references (populated in init)
  // -------------------------------------------------------------------------
  let $pathInput, $assignBtn, $workspaceStatus, $workspaceLabel, $fileCount,
      $reindexBtn, $fileBrowser, $fileList, $fileBrowserEmpty,
      $messages, $welcomeScreen, $thinking, $thinkingText,
      $input, $sendBtn, $newBtn, $statusPill;

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  function init() {
    if (_initialized) return;
    _initialized = true;

    // Bind DOM refs
    $pathInput        = document.getElementById('cowork-path-input');
    $assignBtn        = document.getElementById('cowork-assign-btn');
    $workspaceStatus  = document.getElementById('cowork-workspace-status');
    $workspaceLabel   = document.getElementById('cowork-workspace-label');
    $fileCount        = document.getElementById('cowork-file-count');
    $reindexBtn       = document.getElementById('cowork-reindex-btn');
    $fileBrowser      = document.getElementById('cowork-file-browser');
    $fileList         = document.getElementById('cowork-file-list');
    $fileBrowserEmpty = document.getElementById('cowork-file-browser-empty');
    $messages         = document.getElementById('cowork-messages');
    $welcomeScreen    = document.getElementById('cowork-welcome-screen');
    $thinking         = document.getElementById('cowork-thinking');
    $thinkingText     = document.getElementById('cowork-thinking-text');
    $input            = document.getElementById('cowork-input');
    $sendBtn          = document.getElementById('cowork-send-btn');
    $newBtn           = document.getElementById('cowork-new-btn');
    $statusPill       = document.getElementById('cowork-status-pill');

    if (!$pathInput) return; // guard: DOM not ready

    // Restore last workspace path
    const lastPath = localStorage.getItem(LS_KEY_PATH);
    if (lastPath) $pathInput.value = lastPath;

    // Event bindings
    $assignBtn.addEventListener('click', _onAssign);
    $reindexBtn.addEventListener('click', _onReindex);
    $sendBtn.addEventListener('click', _onSend);
    $newBtn.addEventListener('click', _onNewChat);

    $input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        _onSend();
      }
    });

    $input.addEventListener('input', function () {
      // Auto-grow
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });

    // Wire welcome example cards
    document.querySelectorAll('[data-cowork-prompt]').forEach(function (card) {
      card.addEventListener('click', function () {
        const prompt = this.getAttribute('data-cowork-prompt');
        if (prompt) {
          $input.value = prompt;
          $input.dispatchEvent(new Event('input'));
          _onSend();
        }
      });
    });
  }

  // -------------------------------------------------------------------------
  // Folder assignment
  // -------------------------------------------------------------------------

  async function assignFolder(path) {
    if (!path) return;
    _workspacePath = path;
    localStorage.setItem(LS_KEY_PATH, path);

    _setStatus('Indexando...');
    $assignBtn.disabled = true;

    try {
      // Create a cowork session: POST /api/chat with mode=cowork
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: 'He asignado esta carpeta como workspace. Muéstrame qué archivos contiene.',
          mode: 'cowork',
          project_path: path,
        }),
      });

      if (!resp.ok) {
        throw new Error('Error al crear sesión: ' + resp.status);
      }

      const data = await resp.json();
      _sessionId = data.session_id;
      localStorage.setItem(LS_KEY_SESSION, _sessionId);

      // Enable chat input
      $sendBtn.disabled = false;
      $input.disabled = false;
      $input.focus();

      // Show workspace status bar
      _showWorkspaceStatus(path);

      // Load file list
      await _loadFiles(path);

      // Open SSE for the initial greeting
      _openSSE(_sessionId);

    } catch (err) {
      console.error('[CoWork] assignFolder error:', err);
      _setStatus('Error');
      _appendMessage('system', 'No se pudo asignar el workspace: ' + err.message);
    } finally {
      $assignBtn.disabled = false;
    }
  }

  // -------------------------------------------------------------------------
  // File browser
  // -------------------------------------------------------------------------

  async function _loadFiles(path) {
    try {
      const resp = await fetch('/api/cowork/files?path=' + encodeURIComponent(path));
      if (!resp.ok) {
        _renderFileList([]);
        return;
      }
      const data = await resp.json();
      _renderFileList(data.entries || []);
      if ($fileCount) {
        $fileCount.textContent = data.entry_count + ' archivo' + (data.entry_count !== 1 ? 's' : '');
      }
    } catch (err) {
      console.error('[CoWork] loadFiles error:', err);
      _renderFileList([]);
    }
  }

  function _renderFileList(entries) {
    if (!$fileList) return;

    $fileList.innerHTML = '';

    if (entries.length === 0) {
      $fileBrowserEmpty.style.display = '';
      $fileList.style.display = 'none';
      return;
    }

    $fileBrowserEmpty.style.display = 'none';
    $fileList.style.display = '';

    entries.forEach(function (entry) {
      const li = document.createElement('li');
      li.className = 'cowork-file-item cowork-file-item--' + entry.type;

      const icon = entry.type === 'dir' ? '&#x1f4c1;' : _fileIcon(entry.ext);
      li.innerHTML =
        '<span class="cowork-file-icon">' + icon + '</span>' +
        '<span class="cowork-file-name" title="' + entry.path + '">' + entry.name + '</span>';

      if (entry.type === 'file') {
        li.addEventListener('click', function () {
          $input.value = 'Lee el archivo "' + entry.name + '" y explícame qué contiene.';
          $input.dispatchEvent(new Event('input'));
          $input.focus();
        });
      }

      $fileList.appendChild(li);
    });
  }

  function _fileIcon(ext) {
    const icons = {
      '.md': '&#x1f4dd;', '.txt': '&#x1f4c4;', '.pdf': '&#x1f4d5;',
      '.json': '&#x1f9e9;', '.yaml': '&#x1f9e9;', '.yml': '&#x1f9e9;',
      '.py': '&#x1f40d;', '.js': '&#x1f7e1;', '.ts': '&#x1f537;',
      '.html': '&#x1f30d;', '.csv': '&#x1f4ca;',
    };
    return icons[ext] || '&#x1f4c4;';
  }

  function _showWorkspaceStatus(path) {
    if (!$workspaceStatus) return;
    $workspaceLabel.textContent = path.split(/[/\\]/).pop() || path;
    $workspaceStatus.style.display = '';
  }

  // -------------------------------------------------------------------------
  // Chat
  // -------------------------------------------------------------------------

  function _onSend() {
    if (!$input) return;
    const message = $input.value.trim();
    if (!message || _isThinking) return;
    if (!_sessionId) {
      _appendMessage('system', 'Primero asigna un workspace usando el panel izquierdo.');
      return;
    }

    $input.value = '';
    $input.style.height = 'auto';
    _appendMessage('user', message);
    _sendMessage(message);
  }

  async function _sendMessage(message) {
    _isThinking = true;
    _showThinking('Analizando workspace...');
    $sendBtn.disabled = true;

    // Close any previous SSE
    if (_eventSource) {
      _eventSource.close();
      _eventSource = null;
    }

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, session_id: _sessionId }),
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      const data = await resp.json();
      _openSSE(data.session_id || _sessionId);

    } catch (err) {
      console.error('[CoWork] sendMessage error:', err);
      _hideThinking();
      _isThinking = false;
      $sendBtn.disabled = false;
      _appendMessage('system', 'Error al enviar el mensaje: ' + err.message);
    }
  }

  function _openSSE(sid) {
    if (_eventSource) _eventSource.close();

    _eventSource = new EventSource('/api/chat/stream/' + sid);

    _eventSource.onmessage = function (e) {
      try {
        const evt = JSON.parse(e.data);
        _handleSSEEvent(evt);
      } catch (err) {
        console.warn('[CoWork] SSE parse error:', err);
      }
    };

    _eventSource.onerror = function () {
      _hideThinking();
      _isThinking = false;
      $sendBtn.disabled = false;
      _eventSource.close();
      _eventSource = null;
    };
  }

  function _handleSSEEvent(evt) {
    switch (evt.type) {
      case 'thinking':
        _showThinking(evt.message || 'Pensando...');
        break;

      case 'final_answer':
        _hideThinking();
        _isThinking = false;
        $sendBtn.disabled = false;
        if (evt.content) _appendMessage('assistant', evt.content, evt.metrics);
        break;

      case 'done':
        _hideThinking();
        _isThinking = false;
        $sendBtn.disabled = false;
        if (_eventSource) { _eventSource.close(); _eventSource = null; }
        break;

      case 'error':
        _hideThinking();
        _isThinking = false;
        $sendBtn.disabled = false;
        _appendMessage('system', 'Error: ' + (evt.message || 'Error desconocido'));
        if (_eventSource) { _eventSource.close(); _eventSource = null; }
        break;
    }
  }

  // -------------------------------------------------------------------------
  // Message rendering
  // -------------------------------------------------------------------------

  function _appendMessage(role, content, metrics) {
    if (!$messages) return;

    // Hide welcome screen on first message
    if ($welcomeScreen) $welcomeScreen.style.display = 'none';

    const div = document.createElement('div');
    div.className = 'chat-message chat-message--' + role;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // Render markdown-like content for assistant messages
    if (role === 'assistant') {
      bubble.innerHTML = _renderMarkdown(content);
    } else {
      bubble.textContent = content;
    }

    div.appendChild(bubble);

    if (metrics && role === 'assistant') {
      const meta = document.createElement('div');
      meta.className = 'message-meta';
      meta.textContent = metrics.duration + 's · ' + (metrics.tokens || 0) + ' tokens';
      div.appendChild(meta);
    }

    $messages.appendChild(div);
    $messages.scrollTop = $messages.scrollHeight;
  }

  function _renderMarkdown(text) {
    // Basic markdown rendering (code blocks, bold, lists)
    if (window.marked) {
      try { return window.marked.parse(text); } catch (e) { /* fall through */ }
    }
    // Minimal fallback
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  // -------------------------------------------------------------------------
  // Thinking indicator
  // -------------------------------------------------------------------------

  function _showThinking(msg) {
    if ($thinking) $thinking.style.display = 'flex';
    if ($thinkingText) $thinkingText.textContent = msg || 'Pensando...';
    if ($statusPill) { $statusPill.textContent = 'Analizando'; $statusPill.className = 'agent-pill-status status-busy'; }
  }

  function _hideThinking() {
    if ($thinking) $thinking.style.display = 'none';
    if ($statusPill) { $statusPill.textContent = 'Listo'; $statusPill.className = 'agent-pill-status status-online'; }
  }

  // -------------------------------------------------------------------------
  // Status
  // -------------------------------------------------------------------------

  function _setStatus(text) {
    if ($statusPill) $statusPill.textContent = text;
  }

  // -------------------------------------------------------------------------
  // Event handlers
  // -------------------------------------------------------------------------

  function _onAssign() {
    const path = $pathInput ? $pathInput.value.trim() : '';
    if (path) assignFolder(path);
  }

  async function _onReindex() {
    if (!_workspacePath) return;
    $reindexBtn.textContent = '&#x21bb; Indexando...';
    await _loadFiles(_workspacePath);
    $reindexBtn.innerHTML = '&#x21bb; Reindexar';
  }

  function _onNewChat() {
    // Reset session and chat history
    _sessionId = null;
    _workspacePath = null;
    localStorage.removeItem(LS_KEY_SESSION);
    localStorage.removeItem(LS_KEY_PATH);

    if ($messages) {
      $messages.innerHTML = '';
      if ($welcomeScreen) {
        $welcomeScreen.style.display = '';
        $messages.appendChild($welcomeScreen);
      }
    }
    if ($fileList) $fileList.innerHTML = '';
    if ($fileBrowserEmpty) $fileBrowserEmpty.style.display = '';
    if ($fileList) $fileList.style.display = 'none';
    if ($workspaceStatus) $workspaceStatus.style.display = 'none';
    if ($pathInput) $pathInput.value = '';
    if ($sendBtn) $sendBtn.disabled = true;
    if (_eventSource) { _eventSource.close(); _eventSource = null; }
    _isThinking = false;
    _hideThinking();
  }

  // -------------------------------------------------------------------------
  // Exports
  // -------------------------------------------------------------------------

  return {
    init: init,
    assignFolder: assignFolder,
  };
})();
