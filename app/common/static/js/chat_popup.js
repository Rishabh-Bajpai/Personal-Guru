// app/common/static/js/chat_popup.js

let chatConfig = {};

/**
 * Initializes the chat popup UI by wiring up DOM elements and event handlers.
 *
 * The configuration object is stored in a module-level variable and is used
 * by the chat popup to interact with backend services.
 *
 * @param {{urls: {chat: string}}} config - Configuration for the chat popup.
 * @param {Object} config.urls - Collection of endpoint URLs used by the chat.
 * @param {string} config.urls.chat - URL endpoint used to send chat messages
 *     or interact with the chat backend.
 */
function initChatPopup(config) {
    chatConfig = config;
    const chatLauncher = document.getElementById('chat-launcher');
    const chatPopup = document.getElementById('chat-popup');
    const chatToggleBtn = document.getElementById('chat-toggle-btn');
    const chatMaximizeBtn = document.getElementById('chat-maximize-btn');
    const chatForm = document.getElementById('chat-form-popup');
    const chatInput = document.getElementById('chat-input-popup');
    const chatHistory = document.getElementById('chat-history-popup');
    let isMaximized = false;

    function openChat() {
        chatLauncher.style.display = 'none';
        chatPopup.style.display = 'flex';
        chatPopup.style.transform = 'scale(1)';
        chatPopup.style.opacity = '1';
        chatInput.focus();
    }

    function closeChat() {
        chatPopup.style.transform = 'scale(0.8)';
        chatPopup.style.opacity = '0';
        setTimeout(() => {
            chatPopup.style.display = 'none';
            chatLauncher.style.display = 'flex';
            // Reset to normal size when closing
            if (isMaximized) {
                toggleMaximize();
            }
        }, 200);
    }

    function toggleMaximize() {
        isMaximized = !isMaximized;
        if (isMaximized) {
            chatPopup.classList.add('maximized');
            chatMaximizeBtn.textContent = '◱';
            chatMaximizeBtn.title = 'Restore';
        } else {
            chatPopup.classList.remove('maximized');
            chatMaximizeBtn.textContent = '□';
            chatMaximizeBtn.title = 'Maximize';
        }
    }

    chatLauncher.addEventListener('click', openChat);
    chatToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeChat();
    });
    chatMaximizeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleMaximize();
    });


    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = chatInput.value;
        if (!question.trim()) return;
        chatInput.value = '';

        const userMessage = document.createElement('div');
        userMessage.className = 'chat-message user-message';
        userMessage.innerHTML = `<strong>You:</strong> ${question}`;
        chatHistory.appendChild(userMessage);
        chatHistory.scrollTop = chatHistory.scrollHeight;


        // This is a placeholder for a loader
        const tutorMessage = document.createElement('div');
        tutorMessage.className = 'chat-message bot-message';
        tutorMessage.innerHTML = '<strong>Tutor:</strong> Thinking...';
        chatHistory.appendChild(tutorMessage);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        try {
            const response = await fetch(chatConfig.urls.chat, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                },
                body: JSON.stringify({ question: question })
            });

            const data = await response.json();
            const md = window.markdownit({
                html: false
            });
            const renderedAnswer = md.render(data.answer || '');
            const safeAnswer = window.DOMPurify
                ? window.DOMPurify.sanitize(renderedAnswer)
                : renderedAnswer;
            tutorMessage.innerHTML = `<strong>Tutor:</strong> ${safeAnswer}`;
            chatHistory.scrollTop = chatHistory.scrollHeight;
        } catch (error) {
            tutorMessage.innerHTML = '<strong>Tutor:</strong> Sorry, something went wrong.';
            console.error('Chat error:', error);
        }
    });

    // Initially make sure the launcher is visible and popup is hidden
    chatLauncher.style.display = 'flex';
    chatPopup.style.display = 'none';
    chatPopup.style.opacity = '0';
    chatPopup.style.transform = 'scale(0.8)';
}
