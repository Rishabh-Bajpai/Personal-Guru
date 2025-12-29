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
    setupChat();
}

function toggleSidebar() {
    const sidebar = document.getElementById('plan-sidebar');
    sidebar.classList.toggle('collapsed');
}

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

// Chat Logic
function setupChat() {
    document.getElementById('chat-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        const question = input.value;
        input.value = '';

        const chatHistory = document.getElementById('chat-history');
        const userMessage = document.createElement('div');
        userMessage.className = 'chat-message user-message';
        userMessage.innerHTML = `<strong>You:</strong> ${question}`;
        chatHistory.appendChild(userMessage);

        showLoader();
        try {
            const response = await fetch(config.urls.chat, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify({ question: question })
            });

            const data = await response.json();
            const botMessage = document.createElement('div');
            botMessage.className = 'chat-message bot-message';
            botMessage.innerHTML = `<strong>Bot:</strong> ${md.render(data.answer)}`;
            chatHistory.appendChild(botMessage);
        } finally {
            hideLoader();
        }
    });
}
