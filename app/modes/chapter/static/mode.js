function setupChapterMode(config) {
    document.addEventListener('DOMContentLoaded', function () {
        const generateBtn = document.getElementById('generate-plan');
        const statusDiv = document.getElementById('generation-status');
        const errorDiv = document.getElementById('generation-error');

        // Check if elements exist (might be hidden if plan exists)
        if (!generateBtn) return;

        generateBtn.addEventListener('click', async () => {
            generateBtn.disabled = true;
            statusDiv.style.display = 'block';
            errorDiv.textContent = '';

            try {
                const res = await fetch(config.urls.generate_plan, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic: config.topicName })
                });

                const data = await res.json();

                if (res.ok) {
                    // Reload to show the plan
                    window.location.reload();
                } else {
                    errorDiv.textContent = data.error || 'Error generating plan.';
                    generateBtn.disabled = false;
                    statusDiv.style.display = 'none';
                }
            } catch (e) {
                errorDiv.textContent = "Network error: " + e.toString();
                generateBtn.disabled = false;
                statusDiv.style.display = 'none';
            }
        });
    });
}
