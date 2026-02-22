/**
 * Multimodal Module - OCR and Speech-to-Text Integration
 */
const MultimodalModule = (function() {
    let mediaRecorder;
    let audioChunks = [];

    async function init() {
        console.log("🎙️ MultimodalModule: Initialized");
    }

    async function handleOCR(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            window.showMessage('Extracting text from image...', 'info');
            const response = await fetch('/api/multimodal/ocr', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.text) {
                const input = document.getElementById('chat-input');
                input.value += (input.value ? '
' : '') + data.text;
                input.dispatchEvent(new Event('input')); // Trigger resize
                window.showMessage('Text extracted successfully', 'success');
            }
        } catch (error) {
            window.showMessage('OCR failed: ' + error.message, 'error');
        }
    }

    async function toggleSpeech() {
        const btn = document.getElementById('voice-input-btn');
        
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            btn.classList.remove('recording-active');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                sendAudioToServer(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            btn.classList.add('recording-active');
            window.showMessage('Listening...', 'info');

        } catch (err) {
            window.showMessage('Microphone access denied', 'error');
        }
    }

    async function sendAudioToServer(blob) {
        const formData = new FormData();
        formData.append('audio', blob);

        try {
            const response = await fetch('/api/multimodal/stt', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.text) {
                const input = document.getElementById('chat-input');
                input.value += (input.value ? ' ' : '') + data.text;
                input.dispatchEvent(new Event('input'));
            }
        } catch (error) {
            window.showMessage('Speech recognition failed', 'error');
        }
    }

    return { init, handleOCR, toggleSpeech };
})();

window.MultimodalModule = MultimodalModule;
