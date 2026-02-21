// Knowledge Base logic
document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('kb-upload-zone');
    const fileInput = document.getElementById('kb-file-input');

    async function loadDocuments() {
        const resp = await fetch('/api/knowledge/documents');
        const data = await resp.json();
        const grid = document.getElementById('kb-doc-grid');
        grid.innerHTML = '';
        
        if (data.documents.length === 0) {
            grid.innerHTML = '<p class="placeholder">No documents indexed yet.</p>';
            return;
        }

        data.documents.forEach(doc => {
            const card = document.createElement('div');
            card.className = 'kb-card';
            card.innerHTML = `
                <div class="kb-card-icon">📄</div>
                <div class="kb-card-info">
                    <h4>${doc.filename}</h4>
                    <p>ID: ${doc.id.substring(0, 8)}...</p>
                    <small>${doc.source} - ${doc.timestamp || 'N/A'}</small>
                </div>
                <button class="btn-icon delete" onclick="deleteKbDoc('${doc.id}')">&times;</button>
            `;
            grid.appendChild(card);
        });
    }

    window.deleteKbDoc = async (id) => {
        if (confirm('Delete this document from vector memory?')) {
            await fetch(`/api/knowledge/documents/${id}`, { method: 'DELETE' });
            loadDocuments();
        }
    };

    uploadZone.onclick = () => fileInput.click();
    
    fileInput.onchange = async () => {
        const files = fileInput.files;
        if (files.length === 0) return;

        for (let file of files) {
            const formData = new FormData();
            formData.append('file', file);
            
            uploadZone.classList.add('uploading');
            const resp = await fetch('/api/knowledge/upload', {
                method: 'POST',
                body: formData
            });
            uploadZone.classList.remove('uploading');
            
            const data = await resp.json();
            if (data.status === 'success') {
                console.log(`Indexed ${file.name}`);
            } else {
                alert(`Error indexing ${file.name}: ${data.error}`);
            }
        }
        loadDocuments();
    };

    // Drag & Drop
    uploadZone.ondragover = (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); };
    uploadZone.ondragleave = () => uploadZone.classList.remove('dragover');
    uploadZone.ondrop = (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        fileInput.files = e.dataTransfer.files;
        fileInput.onchange();
    };

    document.addEventListener('viewChanged', (e) => {
        if (e.detail.view === 'knowledge') loadDocuments();
    });
});
