// Document Translator logic
document.addEventListener('DOMContentLoaded', () => {
    async function loadLanguages() {
        const resp = await fetch('/api/translator/languages');
        const data = await resp.json();
        // Populate a dropdown if needed
    }

    window.translateCurrentFile = async (targetLang) => {
        const projectName = currentProject; // From app.js global state
        const filePath = currentFile; // From app.js global state
        
        if (!projectName || !filePath) return alert('Select a file first');
        
        const resp = await fetch('/api/translator/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_name: projectName,
                file_path: filePath,
                target_lang: targetLang
            })
        });
        
        const data = await resp.json();
        if (data.status === 'success') {
            alert(`File translated to ${targetLang}. Created: ${data.output_file}`);
            refreshFileTree();
        } else {
            alert(`Translation failed: ${data.error}`);
        }
    };
});
