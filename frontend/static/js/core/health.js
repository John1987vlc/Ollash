/**
 * Health Module for Ollash Agent
 */
window.HealthModule = (function() {
    let healthHistory = { cpu: [], ram: [], disk: [] };
    
    // DOM Elements
    let healthCpuBar, healthRamBar, healthDiskBar, healthGpuBar;
    let healthCpuVal, healthRamVal, healthDiskVal, healthNetVal, healthGpuVal;

    function init(elements) {
        healthCpuBar = elements.healthCpuBar;
        healthRamBar = elements.healthRamBar;
        healthDiskBar = elements.healthDiskBar;
        healthGpuBar = elements.healthGpuBar;
        healthCpuVal = elements.healthCpuVal;
        healthRamVal = elements.healthRamVal;
        healthDiskVal = elements.healthDiskVal;
        healthNetVal = elements.healthNetVal;
        healthGpuVal = elements.healthGpuVal;
    }

    function updateMetrics(data) {
        if (healthCpuBar) {
            healthCpuBar.style.width = data.cpu + '%';
            healthCpuBar.className = 'health-bar-fill ' + getStatusClass(data.cpu);
        }
        if (healthRamBar) {
            healthRamBar.style.width = data.ram + '%';
            healthRamBar.className = 'health-bar-fill ' + getStatusClass(data.ram);
        }
        if (healthDiskBar) {
            healthDiskBar.style.width = data.disk + '%';
            healthDiskBar.className = 'health-bar-fill ' + getStatusClass(data.disk);
        }
        
        if (healthCpuVal) healthCpuVal.textContent = data.cpu + '%';
        if (healthRamVal) healthRamVal.textContent = data.ram + '%';
        if (healthDiskVal) healthDiskVal.textContent = data.disk + '%';
        if (healthNetVal) healthNetVal.textContent = `Sub: ${data.net_sent} MB | Baj: ${data.net_recv} MB`;

        // Update history for charts
        const metrics = ['cpu', 'ram', 'disk'];
        metrics.forEach(m => {
            healthHistory[m].push(data[m]);
            if (healthHistory[m].length > 20) healthHistory[m].shift();
            renderMiniChart(m);
        });
    }

    function getStatusClass(val) {
        if (val > 80) return 'red';
        if (val > 50) return 'yellow';
        return 'green';
    }

    function renderMiniChart(metric) {
        const barElement = document.getElementById(`health-${metric}`);
        if (!barElement) return;
        const container = barElement.parentElement.parentElement;
        let canvas = container.querySelector('.health-mini-chart');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.className = 'health-mini-chart';
            canvas.width = 60;
            canvas.height = 20;
            container.appendChild(canvas);
        }
        
        const ctx = canvas.getContext('2d');
        const values = healthHistory[metric];
        if (values.length < 2) return;

        const w = canvas.width;
        const h = canvas.height;
        
        ctx.clearRect(0, 0, w, h);
        ctx.beginPath();
        ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#6366f1';
        ctx.lineWidth = 1;
        
        const step = w / (values.length - 1);
        values.forEach((v, i) => {
            const x = i * step;
            const y = h - (v / 100 * h);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    }

    return {
        init: init,
        updateMetrics: updateMetrics
    };
})();
