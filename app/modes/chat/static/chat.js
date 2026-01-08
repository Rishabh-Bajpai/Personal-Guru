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

    // Auto-resize and Keydown logic for main chat input
    const chatInput = document.getElementById('chat-input');

    function resizeInput() {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
    }

    chatInput.addEventListener('input', resizeInput);

    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            // Only submit if not empty
            if (this.value.trim()) {
                document.getElementById('chat-form').requestSubmit();
            }
        }
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

    });

    // Voice Input Logic
    const micButton = document.getElementById('mic-button');
    let mediaRecorder;
    let audioChunks = [];

    if (micButton) {
        micButton.addEventListener('click', async () => {
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
                        const chatInput = document.getElementById('chat-input');
                        const originalPlaceholder = chatInput.placeholder;
                        chatInput.placeholder = "Transcribing...";
                        chatInput.disabled = true;

                        try {
                            const response = await fetch("/api/transcribe", {
                                method: "POST",
                                headers: {
                                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                                },
                                body: formData
                            });

                            if (!response.ok) {
                                throw new Error("Transcription failed");
                            }

                            const data = await response.json();
                            if (data.transcript) {
                                chatInput.value += (chatInput.value ? " " : "") + data.transcript;
                                // Auto-submit: Input must be enabled for it to be included in the form submission
                                chatInput.disabled = false;
                                document.getElementById('chat-form').requestSubmit();
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
});
