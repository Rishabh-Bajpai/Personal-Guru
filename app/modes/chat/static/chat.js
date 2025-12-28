// Initialize markdown-it (same config as Chapter Mode)
const md = window.markdownit({
    html: true,
    linkify: true,
    typographer: true,
    breaks: true
});

function toggleSidebar() {
    const sidebar = document.getElementById('plan-sidebar');
    sidebar.classList.toggle('collapsed');
}

// Extract raw content and render markdown for AI messages
function renderMarkdown() {
    const messages = document.querySelectorAll('.message');

    messages.forEach(function (messageEl) {
        const contentEl = messageEl.querySelector('.message-content');
        const rawEl = messageEl.querySelector('.raw-markdown');

        if (contentEl && rawEl && !contentEl.dataset.rendered) {
            const rawContent = rawEl.textContent;

            if (messageEl.classList.contains('assistant-message')) {
                // Render markdown for assistant messages
                contentEl.innerHTML = md.render(rawContent);
            } else {
                // Plain text for user messages
                contentEl.textContent = rawContent;
            }

            contentEl.dataset.rendered = "true";
        }
    });
}

function scrollToBottom() {
    const chatWindow = document.getElementById('chat-window');
    if (!chatWindow) {
        return;
    }
    const messages = chatWindow.querySelectorAll('.message-wrapper');

    if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];

        // If the last message is from the assistant, scroll to its top
        if (lastMessage.classList.contains('assistant-wrapper')) {
            lastMessage.scrollIntoView({ block: 'start', behavior: 'auto' });
        } else {
            // Otherwise (e.g. user message or empty), scroll to the very bottom
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    renderMarkdown();
    scrollToBottom();

    // Focus input after rendering
    document.getElementById('chat-input').focus();

    // Disable plan modification form while submitting
    document.getElementById('plan-modification-form').addEventListener('submit', function (e) {
        const textarea = document.getElementById('plan-modification-input');
        const button = document.getElementById('plan-modification-button');

        // Prevent submission if textarea is empty
        if (!textarea.value.trim()) {
            e.preventDefault();
            return false;
        }

        // Disable interactions during submission
        button.disabled = true;
        textarea.readOnly = true;
    });

    // Prevent empty submissions and disable input while loading
    document.getElementById('chat-form').addEventListener('submit', function (e) {
        const input = document.getElementById('chat-input');
        const button = document.getElementById('send-button');
        const loading = document.getElementById('loading-indicator');

        // Prevent submission if input is empty
        if (!input.value.trim()) {
            e.preventDefault();
            return false;
        }

        // Store the value before disabling (disabled fields aren't submitted)
        const messageValue = input.value;

        // Show loading state
        button.disabled = true;
        loading.style.display = 'inline';
        input.readOnly = true; // Use readOnly instead of disabled to preserve form value
    });
});
