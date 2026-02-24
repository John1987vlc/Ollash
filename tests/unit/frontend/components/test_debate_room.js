/**
 * Vitest unit tests — DebateRoom component (P8).
 *
 * Tests: message append order, agent-side routing (A vs B),
 * consensus highlight, cleanup on close, HTML escaping.
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { describe, it, expect, beforeAll, beforeEach } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));

beforeAll(() => {
    const src = readFileSync(
        join(__dirname, '../../../../frontend/static/js/components/debate-room.js'),
        'utf8'
    );
    // eslint-disable-next-line no-eval
    eval(src);
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function openRoom(nodeId = 'node-debate-1') {
    window.DebateRoom.open(nodeId);
}

// ---------------------------------------------------------------------------
// open / close
// ---------------------------------------------------------------------------

describe('DebateRoom.open', () => {
    beforeEach(() => {
        // Reset overlay between tests by removing it
        const ov = document.getElementById('debate-room-overlay');
        if (ov) ov.remove();
        // Clear internal state by re-evaluating (reset module state)
        const src = readFileSync(
            join(__dirname, '../../../../frontend/static/js/components/debate-room.js'),
            'utf8'
        );
        // eslint-disable-next-line no-eval
        eval(src);
    });

    it('creates the overlay element and makes it visible', () => {
        openRoom('task-42');
        const ov = document.getElementById('debate-room-overlay');
        expect(ov).not.toBeNull();
        expect(ov.hasAttribute('hidden')).toBe(false);
    });

    it('sets the node ID label', () => {
        openRoom('task-abc');
        const label = document.getElementById('debate-node-id-label');
        expect(label.textContent).toBe('task-abc');
    });

    it('clears previous messages when opened again', () => {
        openRoom('task-1');
        window.DebateRoom.appendMessage(1, 'a', 'architect', 'First argument');
        openRoom('task-2');
        const panelA = document.getElementById('debate-messages-a');
        expect(panelA.children.length).toBe(0);
    });
});

describe('DebateRoom.close', () => {
    it('hides the overlay with the hidden attribute', () => {
        openRoom('task-x');
        window.DebateRoom.close();
        const ov = document.getElementById('debate-room-overlay');
        expect(ov.hasAttribute('hidden')).toBe(true);
    });

    it('does not throw if called before open', () => {
        const src = readFileSync(
            join(__dirname, '../../../../frontend/static/js/components/debate-room.js'),
            'utf8'
        );
        // eslint-disable-next-line no-eval
        eval(src);
        expect(() => window.DebateRoom.close()).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// appendMessage — order and agent-side routing
// ---------------------------------------------------------------------------

describe('DebateRoom.appendMessage', () => {
    beforeEach(() => {
        const ov = document.getElementById('debate-room-overlay');
        if (ov) ov.remove();
        const src = readFileSync(
            join(__dirname, '../../../../frontend/static/js/components/debate-room.js'),
            'utf8'
        );
        // eslint-disable-next-line no-eval
        eval(src);
        openRoom('debate-test');
    });

    it('routes agentRole "a" to panel A', () => {
        window.DebateRoom.appendMessage(1, 'a', 'architect', 'Proposal A');
        const panelA = document.getElementById('debate-messages-a');
        expect(panelA.children.length).toBe(1);
        expect(panelA.textContent).toContain('Proposal A');
    });

    it('routes agentRole "agent_a" to panel A', () => {
        window.DebateRoom.appendMessage(1, 'agent_a', 'developer_0', 'Agent A speaks');
        const panelA = document.getElementById('debate-messages-a');
        expect(panelA.children.length).toBe(1);
    });

    it('routes agentRole "b" to panel B', () => {
        window.DebateRoom.appendMessage(2, 'b', 'auditor', 'Critique B');
        const panelB = document.getElementById('debate-messages-b');
        expect(panelB.children.length).toBe(1);
        expect(panelB.textContent).toContain('Critique B');
    });

    it('preserves message order within a panel', () => {
        window.DebateRoom.appendMessage(1, 'a', 'agent_a', 'First');
        window.DebateRoom.appendMessage(2, 'a', 'agent_a', 'Second');
        window.DebateRoom.appendMessage(3, 'a', 'agent_a', 'Third');
        const panelA = document.getElementById('debate-messages-a');
        const bubbles = panelA.querySelectorAll('.debate-bubble');
        expect(bubbles.length).toBe(3);
        expect(bubbles[0].textContent).toContain('First');
        expect(bubbles[2].textContent).toContain('Third');
    });

    it('displays round number in bubble meta', () => {
        window.DebateRoom.appendMessage(5, 'b', 'auditor_0', 'Round 5 argument');
        const panelB = document.getElementById('debate-messages-b');
        expect(panelB.querySelector('.debate-bubble-meta').textContent).toContain('Round 5');
    });

    it('escapes HTML in argument text', () => {
        window.DebateRoom.appendMessage(1, 'a', 'agent', '<b>XSS</b>');
        const panelA = document.getElementById('debate-messages-a');
        expect(panelA.innerHTML).not.toContain('<b>XSS</b>');
        expect(panelA.innerHTML).toContain('&lt;b&gt;');
    });

    it('does not throw if called before open', () => {
        const src = readFileSync(
            join(__dirname, '../../../../frontend/static/js/components/debate-room.js'),
            'utf8'
        );
        // eslint-disable-next-line no-eval
        eval(src);
        expect(() =>
            window.DebateRoom.appendMessage(1, 'a', 'agent', 'test')
        ).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// showConsensus — consensus highlight
// ---------------------------------------------------------------------------

describe('DebateRoom.showConsensus', () => {
    beforeEach(() => {
        const ov = document.getElementById('debate-room-overlay');
        if (ov) ov.remove();
        const src = readFileSync(
            join(__dirname, '../../../../frontend/static/js/components/debate-room.js'),
            'utf8'
        );
        // eslint-disable-next-line no-eval
        eval(src);
        openRoom('consensus-test');
    });

    it('makes the consensus banner visible', () => {
        window.DebateRoom.showConsensus('Both agents agree on microservices.');
        const banner = document.getElementById('debate-consensus');
        expect(banner.hasAttribute('hidden')).toBe(false);
    });

    it('displays the consensus text', () => {
        window.DebateRoom.showConsensus('Agreed: use PostgreSQL.');
        const txt = document.getElementById('debate-consensus-text');
        expect(txt.textContent).toBe('Agreed: use PostgreSQL.');
    });

    it('uses default text when no argument is given', () => {
        window.DebateRoom.showConsensus('');
        const txt = document.getElementById('debate-consensus-text');
        expect(txt.textContent).toBe('Consensus reached.');
    });

    it('hides consensus banner when opened for next round', () => {
        window.DebateRoom.showConsensus('Done.');
        openRoom('next-debate');
        const banner = document.getElementById('debate-consensus');
        expect(banner.hasAttribute('hidden')).toBe(true);
    });
});
