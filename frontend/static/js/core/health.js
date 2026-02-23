/**
 * Health Module for Ollash Agent - Compact Grid Version
 */
window.HealthModule = (function() {
    // DOM Elements
    let healthCpuVal, healthRamVal, healthDiskVal, healthNetVal;

    function init(elements) {
        healthCpuVal = elements.healthCpuVal;
        healthRamVal = elements.healthRamVal;
        healthDiskVal = elements.healthDiskVal;
        healthNetVal = elements.healthNetVal;
    }

    function updateMetrics(data) {
        if (healthCpuVal) healthCpuVal.textContent = (data.cpu || 0) + '%';
        if (healthRamVal) healthRamVal.textContent = (data.ram || 0) + '%';
        if (healthDiskVal) healthDiskVal.textContent = (data.disk || 0) + '%';
        
        if (healthNetVal) {
            // Show compact net info: e.g. "0.5M" or "102K"
            const totalNet = (data.net_sent || 0) + (data.net_recv || 0);
            if (totalNet > 1) {
                healthNetVal.textContent = totalNet.toFixed(1) + 'M';
            } else {
                healthNetVal.textContent = Math.round(totalNet * 1024) + 'K';
            }
        }
    }

    return {
        init: init,
        updateMetrics: updateMetrics
    };
})();
