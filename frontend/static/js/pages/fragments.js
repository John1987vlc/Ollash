// Fragment Cache logic
document.addEventListener('DOMContentLoaded', () => {
    async function loadFragments() {
        const resp = await fetch('/api/fragments');
        const data = await resp.json();
        const grid = document.getElementById('fragments-grid');
        grid.innerHTML = '';
        
        data.fragments.forEach(frag => {
            const card = document.createElement('div');
            card.className = `fragment-card ${frag.favorite ? 'favorite' : ''}`;
            card.innerHTML = `
                <div class="fragment-header">
                    <span class="type">${frag.type}</span>
                    <span class="lang">${frag.language}</span>
                    <button class="btn-icon star" onclick="toggleFavorite('${frag.key}', ${!frag.favorite})">${frag.favorite ? '★' : '☆'}</button>
                </div>
                <pre><code>${frag.content.substring(0, 200)}${frag.content.length > 200 ? '...' : ''}</code></pre>
                <div class="fragment-footer">Hits: ${frag.hits}</div>
            `;
            grid.appendChild(card);
        });
        if (typeof hljs !== 'undefined') hljs.highlightAll();
    }

    window.toggleFavorite = async (key, favorite) => {
        await fetch('/api/fragments/favorite', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ key, favorite })
        });
        loadFragments();
    };

    document.addEventListener('viewChanged', (e) => {
        if (e.detail.view === 'fragments') loadFragments();
    });
});
