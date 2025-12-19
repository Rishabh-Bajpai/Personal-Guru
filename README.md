# Personalized Learning AI App

This is a Flask-based web application that serves as a proof-of-concept for a personalized learning tool. It uses a multi-agent AI system to create an interactive learning experience tailored to the user's chosen topic.

## Features

- **Dynamic Study Plans:** Enter any topic and receive a custom, step-by-step study plan.
- **Detailed Study Content:** Each step in the study plan now includes detailed content.
- **Interactive Learning:** Progress through the plan one step at a time.
- **Text-to-Speech:** Listen to each learning step with integrated TTS audio.
- **Knowledge Assessment:** Answer multiple-choice questions after each step to test your understanding.
- **Personalized Background:** Set your own background (e.g., "I am a beginner") to tailor the learning content to your level.
- **Adaptive Learning:** The study plan adapts to your performance on the "Check Your Understanding" questions.
- **Q&A Chat:** Ask questions about the study material and get answers from an AI assistant.
- **Instant Feedback:** Receive immediate feedback on your answers.
- **Local AI Integration:** Designed to connect with locally-hosted AI services (LLM, TTS) for privacy and control.
- **Export to Markdown:** At the end of a course, you can export the entire study plan and content to a markdown file, perfect for importing into note-taking apps like Notion, Obsidian, or NotebookLM.
- **Reel Mode:** A TikTok/Reel-style interface for browsing educational short videos.
- **Comprehensive Test Suite:** Includes a full suite of unit tests to verify application logic.

## Enabling HTTPS for Microphone Access, reels and other security features

Modern web browsers require a secure (HTTPS) connection to allow web pages to access the microphone, and to enable reels mode.

### Method A: Self-Signed Certificate (for Local Development)

This is the simplest way to enable HTTPS for local testing.

1.  **Generate the Certificate:**
    The repository includes a script to generate a self-signed certificate.
    ```bash
    python scripts/generate_cert.py
    ```
    This will create a `certs` directory with `cert.pem` and `key.pem` files.

2.  **Run the Application:**
    Start Personal-Guru as you normally would. The Flask server will automatically detect the certificate and start with HTTPS.

3.  **Trust the Certificate in Your Browser:**
    When you navigate to `https://localhost:5002`, your browser will show a privacy warning. You must accept the risk to proceed.

### Method B: Reverse Proxy (for Production)

Using a reverse proxy like Nginx or Caddy is the standard way to handle HTTPS in a production environment. The reverse proxy manages the SSL certificates (e.g., from Let's Encrypt) and forwards traffic to the Personal-Guru application, which can run on standard HTTP.

**General Steps:**

1.  **Run Personal-Guru:** Start the Personal-Guru application on its default port (`5002`) without any SSL context.
2.  **Set Up Reverse Proxy:**
    -   Configure your reverse proxy (e.g., Nginx Proxy Manager, Caddy) to create a new proxy host.
    -   **Domain:** Your public domain (e.g., `personal-guru.your-domain.com`).
    -   **Scheme:** `http`.
    -   **Forward Hostname/IP:** The IP address of the machine running Personal-Guru.
    -   **Forward Port:** `5002`.
    -   **Enable WebSocket Support:** This is critical for the voice communication to work.
3.  **Enable SSL:**
    -   In your reverse proxy's SSL settings, request a new SSL certificate (e.g., using Let's Encrypt).
    -   Enable "Force SSL" and "HTTP/2 Support".

After saving, you can access Personal-Guru securely at your public domain.

## Setup and Installation

Follow these instructions to get the application running on your local machine.

### 1. Clone the Repository

First, clone this repository to your local machine:

```bash
git clone https://github.com/Rishabh-Bajpai/Personal-Guru.git
cd Personal-Guru
```

### 2. Create a Conda Environment

We recommend using Conda to manage your Python environment. Create and activate a new environment with Python 3.9:

```bash
conda create -n Personal-Guru python=3.9
conda activate Personal-Guru
```

### 3. Install Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

The application is configured using a `.env` file. Copy the example file and edit it with the URLs and models for your local AI services.

```bash
cp .env.example .env
```

Now, open the `.env` file and customize the settings. The application uses the OpenAI API protocol for all LLM providers (including Ollama).

**Key Variables:**
- `LLM_ENDPOINT`: The base URL of your LLM provider.
    - For **Ollama**: `http://localhost:11434/v1`
    - For **LMStudio**: `http://localhost:1234/v1`
    - For **OpenAI**: `https://api.openai.com/v1`
    - For **Gemini**: `https://generativelanguage.googleapis.com/v1beta/openai/`
- `LLM_MODEL_NAME`: The name of the model to use (e.g., `llama3`, `gpt-4o`).
- `LLM_API_KEY`: API Key (optional for local providers like Ollama).
- `LLM_NUM_CTX`: Context window size (recommended: `18000` or higher if your hardware supports it).

## Running the Application

To run the application, you need to have three components running: the LLM server, the Coqui TTS server (optional), and the main Flask application.

### 1. LLM Server (Ollama / LMStudio / etc.)

Ensure your LLM server is running and accessible.

**If using Ollama:**
You can install Ollama from [https://ollama.com/](https://ollama.com/).

Run with Docker (GPU support):
```bash
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

### 2. Coqui TTS Server (TTS) (Optional: also experimental)

This service provides high-quality, human-like text-to-speech. The repository includes a `Dockerfile` for Coqui TTS in the `coqui_tts` directory.

First, build the Docker image:

```bash
cd coqui_tts
sudo docker build -t coqui-chanakya-tts .
cd ..
```

Then, run the Docker container:

```bash
sudo docker run -d -p 5001:5002 --gpus all --restart unless-stopped --name coqui-tts-server coqui-chanakya-tts
```

This will start the TTS server on port 5001 of your host machine, connected to port 5002 inside the container.

### 3. Main Application

Once the dependencies are installed and your `.env` file is configured, you can start the Flask development server:

```bash
python app.py
```

The application will be available at `http://127.0.0.1:5002`.

## For Developers: Running Tests

This project includes a comprehensive test suite that mocks the external AI services. This allows you to verify the application's internal logic without needing a live connection to the AI services.

To run the tests, execute the following command in your terminal:

```bash
pytest
```
