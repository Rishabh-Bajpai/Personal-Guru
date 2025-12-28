document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('suggestions-container');
    const list = document.getElementById('suggestions-list');
    const loading = document.getElementById('suggestions-loading');
    const topicInput = document.querySelector('input[name="topic"]');

    if (!container || !list || !loading) return;

    // Show container and loading immediately
    container.style.display = 'block';
    loading.style.display = 'flex';
    list.innerHTML = '';

    try {
        const response = await fetch('/api/suggest-topics');
        const data = await response.json();

        loading.style.display = 'none';

        if (data.error) {
            // Silently fail or minimal error, as it's a suggestion feature
            console.error(data.error);
            list.innerHTML = `<p class="error-text" style="font-size: 0.8em;">Could not load suggestions.</p>`;
            return;
        }

        if (data.suggestions && data.suggestions.length > 0) {
            data.suggestions.forEach(topic => {
                const chip = document.createElement('div');
                chip.className = 'suggestion-chip';
                chip.textContent = topic;
                chip.onclick = () => {
                    topicInput.value = topic;
                    topicInput.focus();
                };
                list.appendChild(chip);
            });
        } else {
            list.innerHTML = '<p style="font-size: 0.8em; color: #666;">No suggestions found.</p>';
        }
    } catch (err) {
        console.error('Error fetching suggestions:', err);
        loading.style.display = 'none';
        list.innerHTML = ''; // Hide entirely on error
    }
});
