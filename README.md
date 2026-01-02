# Personalized Learning AI App

This is a Flask-based web application that serves as a proof-of-concept for a personalized learning tool. It uses a multi-agent AI system to create an interactive learning experience tailored to the user's chosen topic.

## Features

- **User Accounts:** Secure sign-up, login, and profile management.
- **Topic Isolation:** Each user has their own private learning materials and topics.
- **Dynamic Study Plans:** Enter any topic and receive a custom, step-by-step study plan.
- **Detailed Study Content:** Each step in the study plan now includes detailed content.
- **Interactive Learning:** Progress through the plan one step at a time.
- **Text-to-Speech:** Listen to each learning step with integrated TTS audio.
- **Knowledge Assessment:** Answer multiple-choice questions after each step to test your understanding.
- **Personalized Background:** Set your own background (e.g., "I am a beginner") to tailor the learning content to your level.
- **Adaptive Learning:** The study plan adapts to your performance on the "Check Your Understanding" questions.
- **Q&A Chat:** Ask questions about the study material and get answers from an AI assistant.
- **Background Database Viewer:** Admin tool to view, sort, and manage database records (with bulk delete).
- **Instant Feedback:** Receive immediate feedback on your answers.
- **Local AI Integration:** Designed to connect with locally-hosted AI services (LLM, TTS) for privacy and control.
- **Export to Markdown:** At the end of a course, you can export the entire study plan and content to a markdown file, perfect for importing into note-taking apps like Notion, Obsidian, or NotebookLM.
- **Reel Mode:** A TikTok/Reel-style interface for browsing educational short videos.
- **Comprehensive Test Suite:** Includes a full suite of unit tests to verify application logic.

## Software Architecture

We use the [C4 Model](docs/architecture.md) for architectural documentation.
Key architectural decisions are recorded in [docs/adr](docs/adr).

### System Context

```mermaid
C4Context
    title System Context Diagram for Personal Guru

    Person(user, "User", "A person who wants to learn a new topic.")
    System(personal_guru, "Personal Guru", "Generates study plans, quizzes, and flashcards.")

    System_Ext(openai, "LLM Provider", "OpenAI / Ollama / LMStudio")
    System_Ext(youtube, "YouTube", "Provides video content for Reel Mode.")
    System_Ext(coqui, "Coqui TTS", "Text-to-Speech Engine for audio generation.")

    Rel(user, personal_guru, "Uses", "HTTPS")
    Rel(personal_guru, openai, "Generates Content via", "API")
    Rel(personal_guru, youtube, "Search & Embeds", "API")
    Rel(personal_guru, coqui, "Generates Audio via", "API")
```

See [docs/architecture.md](docs/architecture.md) for Container, Component, and Sequence diagrams.

## Installation & Setup

We offer three ways to install Personal Guru, depending on your needs.

### Global Prerequisites (All Methods)

Before starting, ensure you have the following:
1. **Python 3.11** (Required for the Application).
    *   [Download Python](https://www.python.org/downloads/)
2. **Conda** (Required for the Application).
    *   [Download Miniconda](https://docs.conda.io/en/latest/miniconda.html)
3.  **Docker Desktop** (Required for the Database).
    *   [Download Docker](https://www.docker.com/products/docker-desktop/)
4.  **LLM Provider** (One of the following):
    *   [Ollama](https://ollama.com/) (Free, Local - Recommended)
    *   [LM Studio](https://lmstudio.ai/) (Free, Local)
    *   **OpenAI / Gemini API Key or any other openai compatible LLM API Key** (Cloud)

### Getting Started

First, clone the repository and navigate to the project directory:

```bash
git clone https://github.com/Rishabh-Bajpai/Personal-Guru.git
cd Personal-Guru
```

### Method 1: Automatic Setup (Recommended)
Best for most users. An interactive script guides you through the process, setting up the environment and dependencies for you.

- **Linux/Mac**: `./setup.sh`
- **Windows**: `setup.bat`

### Method 2: Docker
Run the entire stack (App + DB + Optional TTS) in containers.

1.  **Configure Environment (Optional)**:
    Create a `.env` file if you want to connect to a specific LLM (e.g. LMStudio on another machine).
    ```bash
    LLM_ENDPOINT=http://192.168.1.50:1234/v1
    ```
    *If not set, it defaults to connecting to your local host's Ollama at port 11434.*

2.  **Run**:
    - **Linux/Mac**: `./start_docker.sh`
    - **Windows**: `start_docker.bat`

    *Note: The script will ask if you want to run in detached mode (background).*

3.  **Access the App**:
    Open your browser and go to:
    - **http://localhost:5011** (or the port defined in your `.env`)
    
    *Tip: You can change the configuration (LLM, Keys, etc.) directly from the UI by clicking "⚙️ Setup Environment" on the home page.*

### Method 3: Manual Installation (For Developers)
If you prefer full control over your environment.

1.  **Create Environment**: `conda create -n Personal-Guru python=3.11 && conda activate Personal-Guru`
2.  **Install Dependencies**: `pip install -r requirements/base.txt` (or `dev.txt`, `prod.txt`)
3.  **Setup Environment Variables**:
    Creating a `.env` file is **optional** as the application has a built-in UI Wizard to help you configure these settings. However, you can configure it manually:
    
    ```bash
    cp .env.example .env
    ```
    
    **Key Variables:**
    - `DATABASE_URL`: Connection string (e.g., `postgresql://postgres:postgres@localhost:5433/personal_guru`).
    - `PORT`: Default `5011`.
    - `LLM_ENDPOINT`:
      - **Ollama**: `http://localhost:11434/v1`
      - **LMStudio**: `http://localhost:1234/v1`
      - **OpenAI**: `https://api.openai.com/v1`
      - **Gemini**: `https://generativelanguage.googleapis.com/v1beta/openai/`
    - `LLM_MODEL_NAME`: e.g., `llama3`, `gpt-4o`.
    
4.  **Database Setup (Docker)**:
    Start the Postgres database using Docker:
    ```bash
    docker compose up -d db
    ```
    *Starts PostgreSQL on `localhost:5433`.*

5.  **Init Database**:
    ```bash
    python scripts/update_database.py
    ```

6.  **Run**:
    ```bash
    python run.py
    ```

## Database Schema

The application uses the following PostgreSQL tables:

- **users**: Stores user accounts and profiles.
- **topics**: Main table for each subject the user is learning.
- **study_steps**: Steps within a study plan (one-to-many from topics).
- **quizzes**: Quizzes generated for a topic.
- **flashcards**: Flashcards for vocabulary terms.
- **chat_sessions**: Stores the conversational history for "Chat Mode" (one-to-one with topics). Note: "Chapter Mode" side-chats are stored directly in `study_steps.chat_history`.

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
    - Configure your reverse proxy (e.g., Nginx Proxy Manager, Caddy) to create a new proxy host.
    - **Domain:** Your public domain (e.g., `personal-guru.your-domain.com`).
    - **Scheme:** `http`.
    - **Forward Hostname/IP:** The IP address of the machine running Personal-Guru.
    - **Forward Port:** `5002`.
    - **Enable WebSocket Support:** This is critical for the voice communication to work.
3.  **Enable SSL:**
    - In your reverse proxy's SSL settings, request a new SSL certificate (e.g., using Let's Encrypt).
    - Enable "Force SSL" and "HTTP/2 Support".

After saving, you can access Personal-Guru securely at your public domain.

## For Developers: Running Tests

This project includes a comprehensive test suite.

### Unit Tests

Unit tests mock external AI services and verify the application's internal logic.

```bash
python -m pytest -m unit
```

### Integration Tests

Integration tests require a live connection to the LLM service. Ensure your LLM provider is running before executing these.

```bash
python -m pytest -m integration
```

### Running All Tests

To run both unit and integration tests:

```bash
python -m pytest
```

### Debugging LLM Responses

You can see the actual responses from the LLM (or mocks) in the terminal by using the `--show-llm-responses` flag. This works for both unit and integration tests.

```bash
python -m pytest -m integration --show-llm-responses -s
```
