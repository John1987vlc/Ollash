/**
 * Vitest unit tests — ToolBelt component (P9).
 *
 * Tests: icon activation on event, auto-dim after completion,
 * unknown tool name fallback, lane creation and cleanup.
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));

beforeAll(() => {
    const src = readFileSync(
        join(__dirname, '../../../../frontend/static/js/components/tool-belt.js'),
        'utf8'
    );
    // eslint-disable-next-line no-eval
    eval(src);
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeContainer() {
    const el = document.createElement('div');
    el.id = 'test-swimlane-container';
    document.body.appendChild(el);
    return el;
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

describe('ToolBelt.init', () => {
    it('accepts a CSS selector string', () => {
        const el = makeContainer();
        expect(() => window.ToolBelt.init('#test-swimlane-container')).not.toThrow();
        el.remove();
    });

    it('accepts a DOM element directly', () => {
        const el = makeContainer();
        expect(() => window.ToolBelt.init(el)).not.toThrow();
        el.remove();
    });
});

// ---------------------------------------------------------------------------
// onToolStarted — icon activation
// ---------------------------------------------------------------------------

describe('ToolBelt.onToolStarted', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        const el = document.createElement('div');
        el.id = 'swimlane';
        document.body.appendChild(el);
        window.ToolBelt.init('#swimlane');
    });

    it('creates a lane for a new agent', () => {
        window.ToolBelt.onToolStarted({ agent_id: 'developer_0', tool_name: 'file_content_generator', task_id: 't1' });
        const lane = document.querySelector('[data-agent-id="developer_0"]');
        expect(lane).not.toBeNull();
    });

    it('adds active class to the tool icon', () => {
        window.ToolBelt.onToolStarted({ agent_id: 'developer_1', tool_name: 'code_patcher', task_id: 't2' });
        const icon = document.querySelector('.tool-belt-icon.active');
        expect(icon).not.toBeNull();
    });

    it('uses a fallback icon for unknown tool names', () => {
        window.ToolBelt.onToolStarted({ agent_id: 'agent_x', tool_name: 'my_custom_tool', task_id: 't3' });
        const lane = document.querySelector('[data-agent-id="agent_x"]');
        expect(lane).not.toBeNull();
        // The fallback emoji ⚙️ should appear in the icon
        expect(lane.innerHTML).toContain('⚙️');
    });

    it('is a no-op when agent_id is missing', () => {
        expect(() => window.ToolBelt.onToolStarted({ tool_name: 'code_patcher' })).not.toThrow();
    });

    it('is a no-op when tool_name is missing', () => {
        expect(() => window.ToolBelt.onToolStarted({ agent_id: 'developer_2' })).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// onToolCompleted — auto-dim after completion
// ---------------------------------------------------------------------------

describe('ToolBelt.onToolCompleted', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        const el = document.createElement('div');
        el.id = 'swimlane';
        document.body.appendChild(el);
        window.ToolBelt.init('#swimlane');
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('removes active class and adds done class', () => {
        // Unique agent_id per test to avoid _lanes state leaking between tests
        window.ToolBelt.onToolStarted({ agent_id: 'completed_a', tool_name: 'rag_context_selector', task_id: 't1' });
        window.ToolBelt.onToolCompleted({ agent_id: 'completed_a', tool_name: 'rag_context_selector', duration_ms: 120 });

        const icon = document.querySelector('.tool-belt-icon');
        expect(icon.classList.contains('active')).toBe(false);
        expect(icon.classList.contains('done')).toBe(true);
    });

    it('removes done class after 3 seconds', () => {
        window.ToolBelt.onToolStarted({ agent_id: 'completed_b', tool_name: 'code_patcher', task_id: 't2' });
        window.ToolBelt.onToolCompleted({ agent_id: 'completed_b', tool_name: 'code_patcher', duration_ms: 50 });

        vi.advanceTimersByTime(3001);
        const icon = document.querySelector('[data-agent-id="completed_b"] .tool-belt-icon');
        expect(icon).not.toBeNull();
        expect(icon.classList.contains('done')).toBe(false);
    });

    it('updates tooltip with duration when duration_ms is provided', () => {
        window.ToolBelt.onToolStarted({ agent_id: 'completed_c', tool_name: 'vulnerability_scanner', task_id: 't3' });
        window.ToolBelt.onToolCompleted({ agent_id: 'completed_c', tool_name: 'vulnerability_scanner', duration_ms: 250 });

        const tip = document.querySelector('[data-agent-id="completed_c"] .tool-belt-tooltip');
        expect(tip).not.toBeNull();
        expect(tip.textContent).toContain('250ms');
    });

    it('is a no-op when the lane does not exist', () => {
        expect(() =>
            window.ToolBelt.onToolCompleted({ agent_id: 'ghost_agent', tool_name: 'code_patcher', duration_ms: 10 })
        ).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// clearLane
// ---------------------------------------------------------------------------

describe('ToolBelt.clearLane', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        const el = document.createElement('div');
        el.id = 'swimlane';
        document.body.appendChild(el);
        window.ToolBelt.init('#swimlane');
    });

    it('removes the lane element from the DOM', () => {
        window.ToolBelt.onToolStarted({ agent_id: 'clear_dev', tool_name: 'file_content_generator', task_id: 't1' });
        expect(document.querySelector('[data-agent-id="clear_dev"]')).not.toBeNull();

        window.ToolBelt.clearLane('clear_dev');
        expect(document.querySelector('[data-agent-id="clear_dev"]')).toBeNull();
    });

    it('is a no-op for a non-existent lane', () => {
        expect(() => window.ToolBelt.clearLane('nonexistent')).not.toThrow();
    });
});
