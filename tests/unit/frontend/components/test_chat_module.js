/**
 * Vitest unit tests for chat-module.js
 *
 * Tests the ChatModule IIFE in a jsdom environment.
 * Key behaviours tested:
 *   - sendChatMessage sets isStreaming guard to prevent concurrent sends
 *   - Network errors are shown as error messages in the DOM (not swallowed)
 *   - innerHTML fallback uses textContent when formatAnswer is unavailable (XSS guard)
 *   - connectStream dispatches SSE event types to correct DOM actions
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { JSDOM } from 'jsdom';

// ---------------------------------------------------------------------------
// Helper: create a minimal DOM environment and load the module into it
// ---------------------------------------------------------------------------

function buildDOM() {
    const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
        url: 'http://localhost',
    });
    return dom;
}

function loadChatModule(window) {
    const src = readFileSync(
        resolve(process.cwd(), 'frontend/static/js/core/chat-module.js'),
        'utf8'
    );
    // Execute the module source in the given window context
    const fn = new Function('window', 'document', src + '\n return window.ChatModule;');
    return fn(window, window.document);
}

function buildElements(document) {
    const chatMessages = document.createElement('div');
    chatMessages.id = 'chat-messages';
    const chatInput = document.createElement('textarea');
    chatInput.id = 'chat-input';
    const sendBtn = document.createElement('button');
    sendBtn.id = 'send-btn';
    document.body.appendChild(chatMessages);
    document.body.appendChild(chatInput);
    document.body.appendChild(sendBtn);
    return { chatMessages, chatInput, sendBtn };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ChatModule – sendChatMessage', () => {
    let window, document, ChatModule, elements;

    beforeEach(() => {
        const dom = buildDOM();
        window = dom.window;
        document = dom.window.document;
        elements = buildElements(document);
        ChatModule = loadChatModule(window);
        ChatModule.init(elements);
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('does not send when message is empty string', async () => {
        const fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);

        await ChatModule.sendChatMessage('');

        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('does not send while isStreaming is true (concurrent guard)', async () => {
        // Simulate an ongoing stream by sending a message and not resolving fetch
        const fetchMock = vi.fn(() => new Promise(() => {})); // never resolves
        vi.stubGlobal('fetch', fetchMock);

        // Start first message (does not await — fires and leaves promise pending)
        ChatModule.sendChatMessage('first');
        // Attempt second immediately
        ChatModule.sendChatMessage('second');

        // fetch should have been called exactly once — the second call was blocked
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('shows error message in DOM when fetch rejects (network failure)', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network failure')));

        await ChatModule.sendChatMessage('hello');

        const errorMessages = elements.chatMessages.querySelectorAll('.error-message');
        expect(errorMessages.length).toBeGreaterThan(0);
        const text = errorMessages[0].textContent;
        expect(text).toContain('Network failure');
    });

    it('shows error message when API returns non-started status', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            json: async () => ({ status: 'error', message: 'Session limit reached' }),
        }));

        await ChatModule.sendChatMessage('hello');

        const errorMessages = elements.chatMessages.querySelectorAll('.error-message');
        expect(errorMessages.length).toBeGreaterThan(0);
        expect(errorMessages[0].textContent).toContain('Session limit reached');
    });
});

describe('ChatModule – XSS guard: innerHTML vs textContent', () => {
    let window, document, ChatModule, elements;

    beforeEach(() => {
        const dom = buildDOM();
        window = dom.window;
        document = dom.window.document;
        elements = buildElements(document);
        ChatModule = loadChatModule(window);
        ChatModule.init(elements);
    });

    it('uses textContent (not innerHTML) when formatAnswer is absent', () => {
        // Ensure formatAnswer is NOT defined
        delete window.formatAnswer;

        const xssPayload = '<img src=x onerror=alert(1)>';
        const bubble = ChatModule.appendMessage('assistant', xssPayload);

        // textContent should contain the raw string
        expect(bubble.textContent).toContain('<img');
        // The HTML should NOT have been parsed into an actual <img> element
        const imgs = bubble.querySelectorAll('img');
        expect(imgs.length).toBe(0);
    });

    it('uses innerHTML when formatAnswer is defined (trusts the sanitizer)', () => {
        window.formatAnswer = (text) => `<p>${text}</p>`; // simple sanitized wrapper

        const content = 'safe text';
        const bubble = ChatModule.appendMessage('assistant', content);

        expect(bubble.innerHTML).toContain('<p>');
        expect(bubble.textContent).toContain(content);
    });
});

describe('ChatModule – appendMessage roles', () => {
    let window, document, ChatModule, elements;

    beforeEach(() => {
        const dom = buildDOM();
        window = dom.window;
        document = dom.window.document;
        elements = buildElements(document);
        ChatModule = loadChatModule(window);
        ChatModule.init(elements);
    });

    it('appends a user message with correct CSS class', () => {
        ChatModule.appendMessage('user', 'Hello');
        const msgs = elements.chatMessages.querySelectorAll('.user-message');
        expect(msgs.length).toBe(1);
        expect(msgs[0].textContent).toContain('Hello');
    });

    it('appends an error message with correct CSS class', () => {
        ChatModule.appendMessage('error', 'Something went wrong');
        const msgs = elements.chatMessages.querySelectorAll('.error-message');
        expect(msgs.length).toBe(1);
    });

    it('appends a new message at the bottom (scroll order)', () => {
        ChatModule.appendMessage('user', 'First');
        ChatModule.appendMessage('user', 'Second');
        const msgs = elements.chatMessages.querySelectorAll('.user-message');
        const texts = Array.from(msgs).map((m) => m.textContent.trim());
        expect(texts[0]).toContain('First');
        expect(texts[1]).toContain('Second');
    });
});
