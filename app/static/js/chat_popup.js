// app/static/js/chat_popup.js

let chatConfig = {};

/**
 * Initialize the chat popup UI and wire up event handlers for sending messages.
 *
 * @param {Object} config - Configuration object for the chat popup.
 * @param {Object} config.urls - Collection of endpoint URLs used by the chat popup.
 * @param {string} config.urls.chat - URL endpoint to which chat questions are POSTed.
 */
function initChatPopup(config) {
    chatConfig = config;
    const chatToggleBtn = document.getElementById('chat-toggle-btn');
    const chatWindow = document.getElementById('chat-window');
    const chatForm = document.getElementById('chat-form-popup');
    const chatInput = document.getElementById('chat-input-popup');
    const chatHistory = document.getElementById('chat-history-popup');
    const chatHeader = document.getElementById('chat-header');

    // Ensure all required DOM elements exist before proceeding
    if (!chatToggleBtn || !chatWindow || !chatForm || !chatInput || !chatHistory || !chatHeader) {
        console.error('Chat popup initialization failed: required DOM elements are missing.');
        return;
    }
    function toggleChatWindow() {
        if (chatWindow.style.display === 'none' || chatWindow.style.display === '') {
            chatWindow.style.display = 'flex';
            chatToggleBtn.textContent = '−'; // Minus sign
        } else {
            chatWindow.style.display = 'none';
            chatToggleBtn.textContent = '+';
        }
    }

    chatHeader.addEventListener('click', toggleChatWindow);


    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = chatInput.value;
        if (!question.trim()) return;
        chatInput.value = '';

        const userMessage = document.createElement('div');
        userMessage.className = 'chat-message user-message';
        userMessage.innerHTML = '<strong>You:</strong> ';
        userMessage.appendChild(document.createTextNode(question));
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

            if (!response.ok) {
                throw new Error(`Chat request failed with status ${response.status}`);
            }
            const data = await response.json();
            if (window.markdownit && typeof window.markdownit === 'function') {
                const md = window.markdownit();
                tutorMessage.innerHTML = `<strong>Tutor:</strong> ${md.render(data.answer)}`;
            } else {
                // Fallback: display plain text if markdown-it is not available
                tutorMessage.textContent = `Tutor: ${data.answer}`;
            }
            chatHistory.scrollTop = chatHistory.scrollHeight;
        } catch (error) {
            tutorMessage.innerHTML = '<strong>Tutor:</strong> Sorry, something went wrong.';
            console.error('Chat error:', error);
        }
    });

    // Initially hide the chat window
    chatWindow.style.display = 'none';
    chatToggleBtn.textContent = '+';
}
