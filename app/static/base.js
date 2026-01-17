const loader = document.getElementById('loader');
function showLoader() {
    if (loader) {
        loader.style.display = 'block';
    }
}
function hideLoader() {
    if (loader) {
        loader.style.display = 'none';
    }
}

const themeSwitcher = document.getElementById('theme-switcher');
const body = document.body;

if (themeSwitcher) {
    themeSwitcher.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        localStorage.setItem('theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
    });
}

// Apply the saved theme on page load
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        body.classList.remove('dark-mode');
    } else {
        body.classList.add('dark-mode');
    }
});

// ===== Feedback Modal =====
const feedbackBtn = document.getElementById('feedback-btn');
const feedbackModal = document.getElementById('feedback-modal');
const feedbackClose = document.getElementById('feedback-close');
const feedbackCancel = document.getElementById('feedback-cancel');
const feedbackForm = document.getElementById('feedback-form');
const feedbackMessage = document.getElementById('feedback-message');
const starRating = document.getElementById('star-rating');
const feedbackRatingInput = document.getElementById('feedback-rating');

// Open modal
if (feedbackBtn && feedbackModal) {
    feedbackBtn.addEventListener('click', () => {
        feedbackModal.classList.add('active');
    });
}

// Close modal
function closeFeedbackModal() {
    if (feedbackModal) {
        feedbackModal.classList.remove('active');
        // Reset form
        if (feedbackForm) feedbackForm.reset();
        if (feedbackMessage) {
            feedbackMessage.className = 'feedback-message';
            feedbackMessage.textContent = '';
        }
        // Reset stars
        if (starRating) {
            starRating.querySelectorAll('.star').forEach(s => s.classList.remove('selected', 'hovered'));
        }
        if (feedbackRatingInput) feedbackRatingInput.value = '0';
    }
}

if (feedbackClose) feedbackClose.addEventListener('click', closeFeedbackModal);
if (feedbackCancel) feedbackCancel.addEventListener('click', closeFeedbackModal);

// Close on backdrop click
if (feedbackModal) {
    feedbackModal.addEventListener('click', (e) => {
        if (e.target === feedbackModal) closeFeedbackModal();
    });
}

// Star rating interaction
if (starRating) {
    const stars = starRating.querySelectorAll('.star');

    stars.forEach(star => {
        star.addEventListener('mouseenter', () => {
            const val = parseInt(star.dataset.value);
            stars.forEach(s => {
                s.classList.toggle('hovered', parseInt(s.dataset.value) <= val);
            });
        });

        star.addEventListener('mouseleave', () => {
            stars.forEach(s => s.classList.remove('hovered'));
        });

        star.addEventListener('click', () => {
            const val = parseInt(star.dataset.value);
            feedbackRatingInput.value = val;
            stars.forEach(s => {
                s.classList.toggle('selected', parseInt(s.dataset.value) <= val);
            });
        });
    });
}

// Form submission
if (feedbackForm) {
    feedbackForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const feedbackType = document.getElementById('feedback-type').value;
        const rating = parseInt(feedbackRatingInput.value) || 0;
        const comment = document.getElementById('feedback-comment').value;

        if (!feedbackType) {
            feedbackMessage.textContent = 'Please select a feedback type.';
            feedbackMessage.className = 'feedback-message error';
            return;
        }

        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({
                    feedback_type: feedbackType,
                    rating: rating,
                    comment: comment
                })
            });

            const data = await response.json();

            if (response.ok) {
                feedbackMessage.textContent = 'Thank you for your feedback! 🎉';
                feedbackMessage.className = 'feedback-message success';
                setTimeout(closeFeedbackModal, 2000);
            } else {
                feedbackMessage.textContent = data.error || 'Failed to submit feedback.';
                feedbackMessage.className = 'feedback-message error';
            }
        } catch (err) {
            feedbackMessage.textContent = 'Network error. Please try again.';
            feedbackMessage.className = 'feedback-message error';
        }
    });
}

// ===== Input Validation (Length & Value) =====
function setupInputValidation() {
    // Select inputs with validation constraints
    const inputs = document.querySelectorAll('input[maxlength], textarea[maxlength], input[min], input[max]');

    const validateInput = (input) => {
        // Generate valid ID for error message
        const inputId = input.id || input.name || Math.random().toString(36).substr(2, 9);
        const errorId = `error-${inputId}`;
        let errorMsg = document.getElementById(errorId);

        let message = null;

        // 1. Length Check
        if (input.hasAttribute('maxlength')) {
            const maxLength = parseInt(input.getAttribute('maxlength'));
            if (input.value.length >= maxLength) {
                message = `Maximum length of ${maxLength} characters reached.`;
            }
        }

        // 2. Value Check (for numbers)
        // Only check if no length error yet, and value is present
        if (!message && input.type === 'number' && input.value !== '') {
            const val = parseFloat(input.value);

            if (input.hasAttribute('min')) {
                const minVal = parseFloat(input.getAttribute('min'));
                if (val < minVal) {
                    message = `Value must be at least ${minVal}.`;
                }
            }

            if (!message && input.hasAttribute('max')) {
                const maxVal = parseFloat(input.getAttribute('max'));
                if (val > maxVal) {
                    message = `Value must be at most ${maxVal}.`;
                }
            }
        }

        // Display or remove error
        if (message) {
            if (!errorMsg) {
                errorMsg = document.createElement('div');
                errorMsg.id = errorId;
                errorMsg.className = 'input-limit-error';
                input.insertAdjacentElement('afterend', errorMsg);
            }
            errorMsg.textContent = message;

            // Apply invalid state
            input.classList.add('input-invalid');
            input.setAttribute('aria-invalid', 'true');
            input.setAttribute('aria-describedby', errorId);
        } else {
            if (errorMsg) {
                errorMsg.remove();
            }
            // Remove invalid state
            input.classList.remove('input-invalid');
            input.removeAttribute('aria-invalid');
            input.removeAttribute('aria-describedby');
        }
    };

    inputs.forEach(input => {
        // Check initial state
        validateInput(input);

        // Listen for updates
        input.addEventListener('input', function () {
            validateInput(this);
        });
    });
}

document.addEventListener('DOMContentLoaded', setupInputValidation);
