function initFlashcardMode(config) {
    document.addEventListener('DOMContentLoaded', function () {
        const generateBtn = document.getElementById('generate-flashcards');
        const container = document.getElementById('flashcard-container');
        const err = document.getElementById('flash-error');
        const termEl = document.getElementById('flash-term');
        const defEl = document.getElementById('flash-definition');
        const indexEl = document.getElementById('flash-index');
        const prevBtn = document.getElementById('prev-card');
        const nextBtn = document.getElementById('next-card');
        const flashcard = document.getElementById('flashcard');

        // Read data from DOM
        const dataEl = document.getElementById('flashcard-data');
        const topicName = dataEl.dataset.topic;
        let existingFlashcards = [];
        try {
            existingFlashcards = JSON.parse(dataEl.dataset.flashcards);
        } catch (e) {
            console.error("Error parsing flashcards JSON", e);
        }

        let cards = [];
        let idx = 0;

        if (existingFlashcards && existingFlashcards.length > 0) {
            cards = existingFlashcards;
            renderCard(idx);
            document.querySelector('.flashcard-controls').style.display = 'none';
        }

        function renderCard(i) {
            if (!cards || cards.length === 0) return;
            const c = cards[i];
            termEl.textContent = c.term;
            defEl.textContent = c.definition;
            indexEl.textContent = `${i + 1} / ${cards.length}`;
            container.style.display = 'block';
            flashcard.classList.remove('flipped');

            // Show export button if on last card
            const exportControls = document.getElementById('export-controls');
            if (i === cards.length - 1) {
                exportControls.style.display = 'block';
            } else {
                exportControls.style.display = 'none';
            }
        }

        flashcard.addEventListener('click', () => {
            flashcard.classList.toggle('flipped');
        });

        prevBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (idx > 0) { idx--; renderCard(idx); }
        });
        nextBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (idx < cards.length - 1) { idx++; renderCard(idx); }
        });

        // Export PDF button handler
        const exportPdfBtn = document.getElementById('export-pdf-btn');
        if (exportPdfBtn) {
            exportPdfBtn.addEventListener('click', (e) => {
                e.preventDefault();
                // Use configured URL if available, fallback to constructing it
                const url = config.urls.export_pdf || `/flashcards/${topicName}/export/pdf`;
                window.open(url, '_blank');
            });
        }

        generateBtn.addEventListener('click', async () => {
            err.textContent = '';
            const sel = document.querySelector('input[name="flashcount"]:checked').value;
            const payload = { topic: topicName, count: sel };
            generateBtn.disabled = true;
            generateBtn.textContent = 'Generating...';
            try {
                const res = await fetch(config.urls.generate, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                    },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok) {
                    cards = data.flashcards || [];
                    if (cards.length === 0) { err.textContent = 'No flashcards generated.'; }
                    idx = 0;
                    renderCard(idx);
                    document.querySelector('.flashcard-controls').style.display = 'none';
                } else {
                    err.textContent = data.error || 'Error generating flashcards';
                }
            } catch (e) {
                err.textContent = e.toString();
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = 'Generate Flashcards';
            }
        });
    });
}
