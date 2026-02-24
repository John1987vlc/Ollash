/**
 * DiffViewer — P6 Unified diff renderer.
 *
 * API:
 *   DiffViewer.parseDiff(text)                      → Array of hunk objects
 *   DiffViewer.render(text)                         → HTMLElement (div.diff-viewer)
 *   DiffViewer.loadForFile(projectName, relPath, container)
 */
(function (global) {
    'use strict';

    function parseDiff(text) {
        if (!text) return [];
        const lines   = text.split('\n');
        const hunks   = [];
        let   current = null;

        for (const line of lines) {
            if (line.startsWith('@@')) {
                current = { header: line, lines: [] };
                hunks.push(current);
            } else if (current) {
                current.lines.push(line);
            }
        }
        return hunks;
    }

    function render(text) {
        const hunks = parseDiff(text);
        const wrap  = document.createElement('div');
        wrap.className = 'diff-viewer';

        if (!hunks.length) {
            const empty = document.createElement('p');
            empty.className = 'diff-empty';
            empty.textContent = 'No diff content.';
            wrap.appendChild(empty);
            return wrap;
        }

        for (const hunk of hunks) {
            const header = document.createElement('div');
            header.className = 'diff-hunk-header';
            header.textContent = hunk.header;
            wrap.appendChild(header);

            const table = document.createElement('table');
            table.className = 'diff-table';

            let oldLine = _hunkStart(hunk.header, 'old');
            let newLine = _hunkStart(hunk.header, 'new');

            for (const line of hunk.lines) {
                const type = line[0];
                const tr   = document.createElement('tr');
                let oldN = '', newN = '';

                if (type === '-') {
                    oldN = oldLine++; tr.className = 'diff-del';
                } else if (type === '+') {
                    newN = newLine++; tr.className = 'diff-add';
                } else {
                    oldN = oldLine++; newN = newLine++; tr.className = 'diff-ctx';
                }

                tr.innerHTML = `
                    <td class="diff-gutter diff-gutter-old">${oldN}</td>
                    <td class="diff-gutter diff-gutter-new">${newN}</td>
                    <td class="diff-sign">${_esc(type)}</td>
                    <td class="diff-code">${_esc(line.slice(1))}</td>`;
                table.appendChild(tr);
            }
            wrap.appendChild(table);
        }
        return wrap;
    }

    async function loadForFile(projectName, relPath, container) {
        if (!container) return;
        container.innerHTML = '<p class="diff-loading">Loading diff…</p>';
        try {
            const r = await fetch(
                `/api/projects/${encodeURIComponent(projectName)}/git/diff/${encodeURIComponent(relPath)}`
            );
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            container.innerHTML = '';
            container.appendChild(render(data.diff || ''));
        } catch (err) {
            container.innerHTML = `<p class="diff-error">Could not load diff: ${err.message}</p>`;
        }
    }

    function _hunkStart(header, side) {
        const m = side === 'old' ? header.match(/-(\d+)/) : header.match(/\+(\d+)/);
        return m ? parseInt(m[1], 10) : 1;
    }

    function _esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    global.DiffViewer = { parseDiff, render, loadForFile };
})(window);
