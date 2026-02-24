/**
 * Vitest unit tests — DiffViewer component (P6).
 *
 * Tests pure-logic functions: parseDiff hunk splitting, line type
 * classification, empty diff handling, and first-commit edge case.
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { describe, it, expect, beforeAll } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load the component into the jsdom window
beforeAll(() => {
    const src = readFileSync(
        join(__dirname, '../../../../frontend/static/js/components/diff-viewer.js'),
        'utf8'
    );
    // eslint-disable-next-line no-eval
    eval(src);
});

// ---------------------------------------------------------------------------
// parseDiff — hunk splitting
// ---------------------------------------------------------------------------

describe('DiffViewer.parseDiff', () => {
    it('returns empty array for empty string', () => {
        expect(window.DiffViewer.parseDiff('')).toEqual([]);
    });

    it('returns empty array for null/undefined', () => {
        expect(window.DiffViewer.parseDiff(null)).toEqual([]);
        expect(window.DiffViewer.parseDiff(undefined)).toEqual([]);
    });

    it('splits a single hunk correctly', () => {
        const diff = [
            '@@ -1,3 +1,4 @@',
            ' context line',
            '-removed line',
            '+added line',
            '+new extra',
        ].join('\n');

        const hunks = window.DiffViewer.parseDiff(diff);
        expect(hunks).toHaveLength(1);
        expect(hunks[0].header).toBe('@@ -1,3 +1,4 @@');
        expect(hunks[0].lines).toHaveLength(4);
    });

    it('splits multiple hunks correctly', () => {
        const diff = [
            '@@ -1,3 +1,3 @@',
            ' ctx',
            '-del',
            '+add',
            '@@ -10,2 +10,2 @@',
            ' ctx2',
            '-del2',
            '+add2',
        ].join('\n');

        const hunks = window.DiffViewer.parseDiff(diff);
        expect(hunks).toHaveLength(2);
        expect(hunks[1].header).toBe('@@ -10,2 +10,2 @@');
    });

    it('ignores lines before the first @@ header (file headers)', () => {
        const diff = [
            '--- a/src/app.py',
            '+++ b/src/app.py',
            '@@ -5,3 +5,4 @@',
            ' line',
        ].join('\n');

        const hunks = window.DiffViewer.parseDiff(diff);
        expect(hunks).toHaveLength(1);
    });

    // Edge case: first commit — only additions, no @@ -N header
    it('handles first-commit diff with only additions', () => {
        const diff = [
            '@@ -0,0 +1,3 @@',
            '+line one',
            '+line two',
            '+line three',
        ].join('\n');

        const hunks = window.DiffViewer.parseDiff(diff);
        expect(hunks).toHaveLength(1);
        expect(hunks[0].lines.every(l => l.startsWith('+'))).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// parseDiff — line type classification
// ---------------------------------------------------------------------------

describe('DiffViewer line type classification via render()', () => {
    it('adds diff-del class to removed lines', () => {
        const diff = '@@ -1,1 +1,0 @@\n-removed line\n';
        const el = window.DiffViewer.render(diff);
        const rows = el.querySelectorAll('tr.diff-del');
        expect(rows.length).toBeGreaterThan(0);
    });

    it('adds diff-add class to added lines', () => {
        const diff = '@@ -1,0 +1,1 @@\n+added line\n';
        const el = window.DiffViewer.render(diff);
        const rows = el.querySelectorAll('tr.diff-add');
        expect(rows.length).toBeGreaterThan(0);
    });

    it('adds diff-ctx class to context lines', () => {
        const diff = '@@ -1,1 +1,1 @@\n unchanged line\n';
        const el = window.DiffViewer.render(diff);
        const rows = el.querySelectorAll('tr.diff-ctx');
        expect(rows.length).toBeGreaterThan(0);
    });
});

// ---------------------------------------------------------------------------
// render — empty diff fallback
// ---------------------------------------------------------------------------

describe('DiffViewer.render', () => {
    it('shows "No diff content." for empty input', () => {
        const el = window.DiffViewer.render('');
        expect(el.querySelector('.diff-empty')).not.toBeNull();
        expect(el.querySelector('.diff-empty').textContent).toBe('No diff content.');
    });

    it('returns a div.diff-viewer element', () => {
        const el = window.DiffViewer.render('@@ -1,1 +1,1 @@\n line\n');
        expect(el.tagName).toBe('DIV');
        expect(el.classList.contains('diff-viewer')).toBe(true);
    });

    it('escapes HTML in code content', () => {
        const diff = '@@ -1,0 +1,1 @@\n+<script>alert(1)</script>\n';
        const el = window.DiffViewer.render(diff);
        // The rendered HTML should not contain a literal <script> tag
        expect(el.innerHTML).not.toContain('<script>');
        expect(el.innerHTML).toContain('&lt;script&gt;');
    });
});
