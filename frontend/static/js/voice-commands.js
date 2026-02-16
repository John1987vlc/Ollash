/**
 * Advanced Voice Commands (F13)
 * Browser-based speech recognition with intent classification.
 */

class VoiceCommandManager {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.onResult = null;
        this.onError = null;
        this._init();
    }

    _init() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn('Speech Recognition not supported in this browser');
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            const confidence = event.results[0][0].confidence;
            this._processVoiceCommand(transcript, confidence);
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isListening = false;
            this._updateUI(false);
            if (this.onError) this.onError(event.error);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            this._updateUI(false);
        };
    }

    start() {
        if (!this.recognition || this.isListening) return;
        this.recognition.start();
        this.isListening = true;
        this._updateUI(true);
    }

    stop() {
        if (!this.recognition || !this.isListening) return;
        this.recognition.stop();
        this.isListening = false;
        this._updateUI(false);
    }

    toggle() {
        if (this.isListening) {
            this.stop();
        } else {
            this.start();
        }
    }

    async _processVoiceCommand(transcript, confidence) {
        const indicator = document.getElementById('voice-transcript');
        if (indicator) indicator.textContent = transcript;

        try {
            const resp = await fetch('/api/v1/voice/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcript, confidence }),
            });
            const data = await resp.json();

            if (this.onResult) {
                this.onResult({
                    transcript,
                    confidence,
                    command: data.command || data,
                });
            }

            this._showCommandFeedback(data);
        } catch (err) {
            console.error('Voice command processing failed:', err);
            // Fallback: send as chat message
            this._fallbackToChat(transcript);
        }
    }

    _showCommandFeedback(data) {
        const feedbackEl = document.getElementById('voice-feedback');
        if (!feedbackEl) return;

        const type = data.command_type || data.type || 'UNKNOWN';
        const desc = data.action_description || data.description || '';
        feedbackEl.innerHTML = `<span class="voice-cmd-type">${type}</span> ${desc}`;
        feedbackEl.style.display = 'block';

        setTimeout(() => {
            feedbackEl.style.display = 'none';
        }, 4000);
    }

    _fallbackToChat(transcript) {
        const chatInput = document.getElementById('user-input');
        if (chatInput) {
            chatInput.value = transcript;
            const sendBtn = document.getElementById('send-btn');
            if (sendBtn) sendBtn.click();
        }
    }

    _updateUI(listening) {
        const btn = document.getElementById('voice-toggle-btn');
        if (btn) {
            btn.classList.toggle('listening', listening);
            btn.title = listening ? 'Stop Listening' : 'Start Voice Command';
        }
    }
}

window.VoiceCommandManager = VoiceCommandManager;
