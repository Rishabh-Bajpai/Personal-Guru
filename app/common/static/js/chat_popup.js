// app/common/static/js/chat_popup.js

let chatConfig = {};
let isInitialized = false;

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

    // Prevent multiple initializations to avoid duplicate event listeners
    if (isInitialized) {
        console.warn('Chat popup already initialized. Updating configuration only.');
        return;
    }
    const chatLauncher = document.getElementById('chat-launcher');
    const chatPopup = document.getElementById('chat-popup');
    const chatToggleBtn = document.getElementById('chat-toggle-btn');
    const chatMaximizeBtn = document.getElementById('chat-maximize-btn');
    const chatForm = document.getElementById('chat-form-popup');
    const chatInput = document.getElementById('chat-input-popup');
    const chatHistory = document.getElementById('chat-history-popup');
    let isMaximized = false;

    const missingElements = [];
    if (!chatLauncher) missingElements.push('chat-launcher');
    if (!chatPopup) missingElements.push('chat-popup');
    if (!chatToggleBtn) missingElements.push('chat-toggle-btn');
    if (!chatMaximizeBtn) missingElements.push('chat-maximize-btn');
    if (!chatForm) missingElements.push('chat-form-popup');
    if (!chatInput) missingElements.push('chat-input-popup');
    if (!chatHistory) missingElements.push('chat-history-popup');

    if (missingElements.length > 0) {
        console.error(
            'Chat popup initialization failed. Missing required element(s): ' +
            missingElements.join(', ')
        );
        return;
    }
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
        // Recalculate input height as width might have changed
        // setTimeout(updatePopupScrollIndicators, 100);
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

        // Disable input and submit button during request
        const submitButton = chatForm.querySelector('button[type="submit"]');
        const micButton = document.getElementById('mic-button-popup');

        chatInput.disabled = true;
        if (submitButton) submitButton.disabled = true;
        if (micButton) micButton.disabled = true;

        const userMessage = document.createElement('div');
        userMessage.className = 'chat-message user-message';
        userMessage.innerHTML = '<strong>You:</strong> ';
        userMessage.appendChild(document.createTextNode(question));
        chatHistory.appendChild(userMessage);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        // This is a placeholder for a loader
        const tutorMessage = document.createElement('div');
        tutorMessage.className = 'chat-message tutor-message';
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
                throw new Error(`Chat request failed with status ${response.status} ${response.statusText}`);
            }
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
        } finally {
            // Re-enable input and submit button after request completes
            chatInput.disabled = false;
            if (submitButton) submitButton.disabled = false;
            if (micButton) micButton.disabled = false;
            chatInput.focus();
        }
    });

    // Scroll Indicator Logic - Removed as we now use native scrollbar
    // Auto-resize logic
    function handlePopupInput() {
        chatInput.style.height = 'auto';

        const POPUP_INPUT_MAX_HEIGHT = 142;
        const scrollHeight = chatInput.scrollHeight;

        chatInput.style.height = Math.min(scrollHeight, POPUP_INPUT_MAX_HEIGHT) + 'px';

        // Hide scrollbar if content fits, show if it overflows
        chatInput.style.overflowY = scrollHeight > POPUP_INPUT_MAX_HEIGHT ? 'auto' : 'hidden';
    }

    chatInput.addEventListener('input', handlePopupInput);

    // Change cursor to default when hovering over scrollbar
    chatInput.addEventListener('mousemove', function (e) {
        // clientWidth excludes scrollbar, offsetWidth includes it
        const isOverScrollbar = e.offsetX > this.clientWidth || e.offsetY > this.clientHeight;
        this.style.cursor = isOverScrollbar ? 'default' : 'text';
    });

    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (this.value.trim()) {
                chatForm.requestSubmit();
            }
        }
    });

    // Reset height on submit
    chatForm.addEventListener('submit', () => {
        setTimeout(() => {
            chatInput.style.height = 'auto';
        }, 0);
    });

    // Initially make sure the launcher is visible and popup is hidden
    chatLauncher.style.display = 'flex';
    chatPopup.style.display = 'none';
    chatPopup.style.opacity = '0';
    chatPopup.style.transform = 'scale(0.8)';


    // Voice Input Logic
    const micButton = document.getElementById('mic-button-popup');
    let mediaRecorder;
    let audioChunks = [];

    if (micButton) {
        micButton.addEventListener('click', async (e) => {
            e.preventDefault(); // Prevent form submission if inside form
            if (!mediaRecorder || mediaRecorder.state === "inactive") {
                // Start Recording
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.addEventListener("dataavailable", event => {
                        audioChunks.push(event.data);
                    });

                    mediaRecorder.addEventListener("stop", async () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        const formData = new FormData();
                        formData.append("audio", audioBlob, "recording.wav");

                        // Show some loading state on input
                        const chatInput = document.getElementById('chat-input-popup');
                        const originalPlaceholder = chatInput.placeholder;
                        chatInput.placeholder = "Transcribing...";
                        chatInput.disabled = true;

                        try {
                            // Use X-CSRFToken from meta tag
                            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

                            const response = await fetch("/api/transcribe", {
                                method: "POST",
                                headers: {
                                    'X-CSRFToken': csrfToken
                                },
                                body: formData
                            });

                            if (!response.ok) {
                                throw new Error("Transcription failed");
                            }

                            const data = await response.json();
                            if (data.transcript) {
                                chatInput.value += (chatInput.value ? " " : "") + data.transcript;
                                // Auto-submit
                                chatForm.requestSubmit();
                            } else if (data.error) {
                                console.error("Transcription error:", data.error);
                                alert("Transcription failed: " + data.error);
                            }

                        } catch (err) {
                            console.error("Error sending audio:", err);
                            alert("Error sending audio: " + err);
                        } finally {
                            chatInput.disabled = false;
                            chatInput.placeholder = originalPlaceholder;
                            chatInput.focus();
                            // Stop all tracks to release microphone
                            stream.getTracks().forEach(track => track.stop());
                        }
                    });

                    mediaRecorder.start();
                    micButton.textContent = "⏹️"; // Stop icon
                    micButton.classList.add("recording");

                } catch (err) {
                    console.error("Error accessing microphone:", err);
                    alert("Could not access microphone.");
                }
            } else {
                // Stop Recording
                mediaRecorder.stop();
                micButton.textContent = "🎙️";
                micButton.classList.remove("recording");
            }
        });
    }

    // Mark as initialized to prevent duplicate event listeners
    isInitialized = true;
}
