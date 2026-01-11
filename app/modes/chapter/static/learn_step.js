// Markdown Configuration
const md = window.markdownit({
    highlight: function (str, lang) {
        return '<pre class="code-block" data-lang="' + lang + '"><code>' +
            md.utils.escapeHtml(str) +
            '</code></pre>';
    }
});

let config = {};

function initLearnStep(cfg) {
    config = cfg;

    // Initialize Markdown Rendering
    const markdownContent = document.getElementById('step-content-markdown').textContent;
    const renderedContent = document.getElementById('step-content-rendered');
    renderedContent.innerHTML = md.render(markdownContent);

    setupCodeExecution(renderedContent);
    setupReadAloud(markdownContent);
    setupPodcast();
    setupSelectionMenu();
}

function toggleSidebar() {
    const sidebar = document.getElementById('plan-sidebar');
    sidebar.classList.toggle('collapsed');
}

// Plan Modification Logic (Chapter Mode)
document.addEventListener('DOMContentLoaded', () => {
    const planInput = document.getElementById('plan-modification-input');
    const planForm = document.getElementById('plan-modification-form');

    if (planInput && planForm) {
        // Keydown for Shift+Enter
        planInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (this.value.trim()) {
                    planForm.requestSubmit();
                }
            }
        });

        // Auto-resize
        planInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        });

        // Disable input and button on submit
        planForm.addEventListener('submit', function () {
            const btn = document.getElementById('plan-modification-button');
            if (btn) {
                btn.disabled = true;
                btn.innerText = 'Updating Plan...';
            }
            planInput.disabled = true;
        });
    }
});

// Code Execution Logic
function setupCodeExecution(renderedContent) {
    const codeBlocks = renderedContent.querySelectorAll('pre code');
    codeBlocks.forEach((block, index) => {
        const pre = block.parentElement;
        const wrapper = document.createElement('div');
        wrapper.className = 'code-execution-wrapper';
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        const btn = document.createElement('button');
        btn.className = 'execute-button';
        btn.innerText = 'Execute Code';
        btn.onclick = () => executeCode(block.textContent);
        wrapper.appendChild(btn);
    });

    setupSidePanel();
}

async function executeCode(code) {
    openSidePanel();
    const contentDiv = document.getElementById('side-panel-content');
    contentDiv.innerHTML = '<div class="spinner" style="position: relative; top: 0; left: 0; margin: 20px auto;"></div><p>Enhancing and running code...</p>';

    try {
        const response = await fetch(config.urls.execute_code, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            },
            body: JSON.stringify({ code: code })
        });

        const data = await response.json();

        if (response.ok) {
            renderExecutionResult(data);
        } else {
            contentDiv.innerHTML = `<p class="generation-error">Error: ${data.error || 'Unknown error'}</p>`;
        }
    } catch (error) {
        contentDiv.innerHTML = `<p class="generation-error">Network Error: ${error.message}</p>`;
    }
}

function renderExecutionResult(data) {
    const contentDiv = document.getElementById('side-panel-content');
    contentDiv.innerHTML = '';

    if (data.images && data.images.length > 0) {
        const imgHeader = document.createElement('h4');
        imgHeader.innerText = "Visualizations";
        contentDiv.appendChild(imgHeader);

        data.images.forEach(b64 => {
            const img = document.createElement('img');
            img.src = `data:image/png;base64,${b64}`;
            img.className = 'output-image';
            contentDiv.appendChild(img);
        });
    }

    if (data.output) {
        const outHeader = document.createElement('h4');
        outHeader.innerText = "Output";
        contentDiv.appendChild(outHeader);

        const outBlock = document.createElement('div');
        outBlock.className = 'output-block';
        outBlock.innerText = data.output;
        contentDiv.appendChild(outBlock);
    }

    const codeHeader = document.createElement('h4');
    codeHeader.innerText = "Enhanced Code";
    contentDiv.appendChild(codeHeader);

    const codeBlock = document.createElement('pre');
    codeBlock.className = 'output-block';
    codeBlock.innerText = data.enhanced_code;
    contentDiv.appendChild(codeBlock);

    if (data.error && data.error.trim() !== "") {
        const errHeader = document.createElement('h4');
        errHeader.style.color = 'red';
        errHeader.innerText = "Execution Errors";
        contentDiv.appendChild(errHeader);

        const errBlock = document.createElement('div');
        errBlock.className = 'output-block';
        errBlock.style.borderColor = 'red';
        errBlock.innerText = data.error;
        contentDiv.appendChild(errBlock);
    }
}

// Side Panel UI
let sidePanel;
function setupSidePanel() {
    sidePanel = document.getElementById('execution-side-panel');
    if (sidePanel.parentElement !== document.body) {
        document.body.appendChild(sidePanel);
    }

    const closeBtn = sidePanel.querySelector('.button.secondary');
    if (closeBtn) {
        closeBtn.onclick = closeSidePanel;
    }

    // Resizing Logic
    const handle = document.getElementById('resize-handle');
    let isResizing = false;

    handle.addEventListener('mousedown', (e) => {
        isResizing = true;
        sidePanel.style.transition = "none";
        document.body.style.transition = "none";
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', () => {
            isResizing = false;
            sidePanel.style.transition = "transform 0.3s ease-in-out";
            document.body.style.transition = "padding-right 0.3s ease-in-out";
            document.removeEventListener('mousemove', handleMouseMove);
        });
        e.preventDefault();
    });

    function handleMouseMove(e) {
        if (!isResizing) return;
        const newWidth = window.innerWidth - e.clientX;
        if (newWidth > 300 && newWidth < window.innerWidth - 100) {
            sidePanel.style.width = `${newWidth}px`;
            document.body.style.paddingRight = `${newWidth}px`;
        }
    }
}

function openSidePanel() {
    if (!sidePanel) sidePanel = document.getElementById('execution-side-panel');
    sidePanel.classList.add('open');
    const width = sidePanel.offsetWidth;
    document.body.style.transition = "padding-right 0.3s ease-in-out";
    document.body.style.paddingRight = width + "px";
}

function closeSidePanel() {
    if (!sidePanel) sidePanel = document.getElementById('execution-side-panel');
    sidePanel.classList.remove('open');
    document.body.style.paddingRight = "0";
}

// Audio / Read Aloud Logic
function setupReadAloud(markdownContent) {
    const readAloudSwitch = document.getElementById('read-aloud-switch');
    const readButton = document.getElementById('read-button');
    const audioPlayer = document.getElementById('audio-player');

    async function generateAndPlayAudio() {
        showLoader();
        try {
            const response = await fetch(config.urls.generate_audio, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify({ text: markdownContent })
            });
            const data = await response.json();
            if (data.audio_url) {
                audioPlayer.src = data.audio_url;
                audioPlayer.play();
            }
        } finally {
            hideLoader();
        }
    }

    if (sessionStorage.getItem('readAloud') === 'true') {
        readAloudSwitch.checked = true;
        generateAndPlayAudio();
    }

    readAloudSwitch.addEventListener('change', function () {
        sessionStorage.setItem('readAloud', this.checked);
        if (this.checked) {
            generateAndPlayAudio();
        } else {
            audioPlayer.pause();
        }
    });

    readButton.addEventListener('click', generateAndPlayAudio);
}

// Podcast Logic
function setupPodcast() {
    const generateBtn = document.getElementById('generate-podcast-btn');
    const playerContainer = document.getElementById('podcast-player-container');
    const audio = document.getElementById('podcast-audio');
    const playBtn = document.getElementById('podcast-play-btn');
    const progressBar = document.getElementById('podcast-progress-bar');
    const progressFill = document.getElementById('podcast-progress-fill');
    const currentTimeEl = document.getElementById('podcast-current-time');
    const durationEl = document.getElementById('podcast-duration');

    if (!generateBtn) return;

    generateBtn.addEventListener('click', async () => {
        // Show loading state
        const originalText = generateBtn.innerHTML;
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span class="loader-small"></span> Generating...';

        try {
            const response = await fetch(config.urls.generate_podcast, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                }
            });
            const data = await response.json();

            if (data.audio_url) {
                // Initialize player
                initPlayer(data.audio_url);
                generateBtn.style.display = 'none';
                playerContainer.style.display = 'flex';
            } else {
                alert('Error generating podcast: ' + (data.error || 'Unknown error'));
                generateBtn.disabled = false; // Re-enable if error
                generateBtn.innerHTML = originalText;
            }
        } catch (e) {
            alert('Network error: ' + e.message);
            generateBtn.disabled = false;
            generateBtn.innerHTML = originalText;
        }
    });

    // Check if audio already exists (reloaded from DB)
    if (audio.src && audio.src.length > 0 && audio.src !== window.location.href) {
        initPlayer(audio.src, false);
    }

    function initPlayer(url, autoplay = true) {
        audio.src = url;
        audio.load();

        playBtn.onclick = togglePlay;
        progressBar.onclick = seek;
        audio.ontimeupdate = updateProgress;
        audio.onloadedmetadata = () => {
            durationEl.textContent = formatTime(audio.duration);
        };
        audio.onended = () => {
            updatePlayIcon(false);
            progressFill.style.width = '0%';
        };

        // Auto-play
        if (autoplay) {
            togglePlay();
        } else {
            updatePlayIcon(false);
        }
    }

    function togglePlay() {
        if (audio.paused) {
            audio.play();
            updatePlayIcon(true);
        } else {
            audio.pause();
            updatePlayIcon(false);
        }
    }

    function updatePlayIcon(isPlaying) {
        if (isPlaying) {
            playBtn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>'; // Pause icon
        } else {
            playBtn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>'; // Play icon
        }
    }

    function updateProgress() {
        if (audio.duration) {
            const percent = (audio.currentTime / audio.duration) * 100;
            progressFill.style.width = `${percent}%`;
            currentTimeEl.textContent = formatTime(audio.currentTime);
        }
    }

    function seek(e) {
        const percent = e.offsetX / progressBar.offsetWidth;
        audio.currentTime = percent * audio.duration;
    }

    function formatTime(seconds) {
        const min = Math.floor(seconds / 60);
        const sec = Math.floor(seconds % 60);
        return `${min}:${sec < 10 ? '0' + sec : sec}`;
    }
}

// Ask Personal Guru Selection Menu
function setupSelectionMenu() {
    // 1. Create the button dynamically
    let guruBtn = document.createElement('button');
    guruBtn.className = 'guru-ask-btn';
    guruBtn.innerHTML = 'Ask the Personal Guru';
    document.body.appendChild(guruBtn);

    const contentArea = document.querySelector('.learning-content');

    // 2. Handle Selection
    function handleSelection() {
        const selection = window.getSelection();

        // Basic Validation
        if (!selection.rangeCount || selection.isCollapsed) {
            hideButton();
            return;
        }

        const range = selection.getRangeAt(0);
        const selectedText = selection.toString().trim();

        // Check if selection is within learning content
        if (!contentArea.contains(range.commonAncestorContainer)) {
            hideButton();
            return;
        }

        if (selectedText.length === 0) {
            hideButton();
            return;
        }

        // 3. Position Button
        const rect = range.getBoundingClientRect();

        // Calculate position: Centered above the selection
        // We use fixed positioning, so client rects are perfect
        const btnHeight = 40; // Approx height
        const btnWidth = 200; // Approx width to center

        let top = rect.top - btnHeight - 10;
        let left = rect.left + (rect.width / 2) - (guruBtn.offsetWidth / 2);

        // Ensure not off-screen
        if (top < 10) top = rect.bottom + 10; // Show below if too high up
        if (left < 10) left = 10;
        if (left + guruBtn.offsetWidth > window.innerWidth) left = window.innerWidth - guruBtn.offsetWidth - 10;

        guruBtn.style.top = `${top}px`;
        guruBtn.style.left = `${left}px`;

        showButton();
    }

    function showButton() {
        guruBtn.classList.add('visible');
    }

    function hideButton() {
        guruBtn.classList.remove('visible');
    }

    // Events
    if (contentArea) {
        contentArea.addEventListener('mouseup', () => {
            // Small delay to ensure selection is final
            setTimeout(handleSelection, 10);
        });

        contentArea.addEventListener('keyup', (e) => {
            if (e.key === 'Shift' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                setTimeout(handleSelection, 10);
            }
        });
    }

    // Hide when clicking elsewhere
    document.addEventListener('mousedown', (e) => {
        if (e.target !== guruBtn) {
            // Delay hiding so button click can register
            // We don't hide immediately on mousedown if it is the button, 
            // but if it is not the button, we hide.
            // Actually, selection clears on mousedown usually, so we rely on selection change mainly,
            // but let's be explicit.
            if (!guruBtn.contains(e.target)) {
                hideButton();
            }
        }
    });

    // Also listen for selectionchange on document to hide if selection is cleared
    document.addEventListener('selectionchange', () => {
        const selection = window.getSelection();
        if (selection.isCollapsed) {
            hideButton();
        }
    });

    // 4. Click Handler
    guruBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation(); // Prevent clearing selection immediately if needed

        const selection = window.getSelection();
        const text = selection.toString().trim();

        if (text) {
            openChatAndPaste(text);
        }

        hideButton();
        selection.removeAllRanges(); // Clear selection after asking
    });

    function openChatAndPaste(text) {
        const chatPopup = document.getElementById('chat-popup');
        const chatLauncher = document.getElementById('chat-launcher');
        const chatInput = document.getElementById('chat-input-popup');

        if (!chatPopup || !chatInput) return;

        // Open chat if closed
        if (chatPopup.style.display === 'none' || chatPopup.style.display === '') {
            if (chatLauncher) chatLauncher.click();
        }

        // Paste text
        chatInput.value = text;
        chatInput.focus();

        // Optional: Dispatch input event if you have auto-resize logic bound to it
        chatInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
}
