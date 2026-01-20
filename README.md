# Personalized Learning AI App

This is a Flask-based web application that serves as a proof-of-concept for a personalized learning tool. It uses a multi-agent AI system to create an interactive learning experience tailored to the user's chosen topic.

# For live demo: [https://pg-demo.samosa-ai.com/](https://pg-demo.samosa-ai.com)

## Features

- **User Accounts:** Secure sign-up, login, and profile management.
- **Topic Isolation:** Each user has their own private learning materials and topics.
- **Dynamic Study Plans:** Enter any topic and receive a custom, step-by-step study plan.
- **Detailed Study Content:** Each step in the study plan now includes detailed content.
- **Interactive Learning:** Progress through the plan one step at a time.
- **Text-to-Speech:** Listen to each learning step with integrated TTS audio.
- **Podcast Generation:** transform any topic into a dialogue-based audio podcast for on-the-go learning.
- **Voice Input (STT):** Use your microphone to interact with the AI assistant and navigation.
- **Flashcards:** Review vocabulary and key concepts with interactive flashcards.
- **Code Sandbox:** Execute Python code securely within the application for interactive learning.
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


## Installation & Setup

We offer three ways to install Personal Guru, depending on your needs.

### Global Prerequisites (All Methods)

Before starting, ensure you have the following:

1. **Conda** (Required for the Application).
    - [Download Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2. **Docker Desktop** (Required for the Database).
    - [Download Docker](https://www.docker.com/products/docker-desktop/)
3. **FFmpeg** (Required for Audio Processing).
    - **Linux**: `sudo apt install ffmpeg`
    - **Mac**: `brew install ffmpeg`
    - **Windows**: `winget install ffmpeg` or [Download from ffmpeg.org](https://ffmpeg.org/download.html)
4. **LLM Provider** (One of the following):
    - [Ollama](https://ollama.com/) (Free, Local - Recommended)
    - [LM Studio](https://lmstudio.ai/) (Free, Local)
    - **OpenAI / Gemini API Key or any other openai compatible LLM API Key** (Cloud)

### Getting Started

First, clone the repository and navigate to the project directory:

```bash
git clone https://github.com/Rishabh-Bajpai/Personal-Guru.git
cd Personal-Guru
```

### Method 1: Automatic Setup (Recommended)

Best for most users. An interactive script guides you through the process, setting up the environment and dependencies for you.

- **Linux/Mac**: `bash scripts/installation/setup.sh`
- **Windows**: `scripts\installation\setup.bat`

### Method 2: Docker

Run the entire stack (App + DB + Optional TTS) in containers.

1. **Configure Environment (Optional)**:
    Create a `.env` file if you want to connect to a specific LLM (e.g. LMStudio on another machine).

    ```bash
    LLM_BASE_URL=http://localhost:1234/v1
    ```

    *If not set, it defaults to connecting to your local host's Ollama at port 11434.*

2. **Run**:
    - **Linux/Mac**: `bash scripts/installation/start_docker.sh`
    - **Windows**: `scripts\installation\start_docker.bat`

    *Note: The script will ask if you want to run in detached mode (background).*

3. **Access the App**:
    Open your browser and go to:
    - **<http://localhost:5011>** (or the port defined in your `.env`)

    *Tip: You can change the configuration (LLM, Keys, etc.) directly from the UI by clicking "⚙️ Setup Environment" on the home page.*

### Method 3: Manual Installation (For Developers)

If you prefer full control over your environment or want to contribute, please check our **[Contribution Guide](CONTRIBUTING.md)** for detailed setup instructions.

Below is a quick summary for manual setup:

1. **Create Environment**: `conda create -n Personal-Guru python=3.11 && conda activate Personal-Guru`
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Setup Environment Variables**:
    Creating a `.env` file is **optional** as the application has a built-in UI Wizard to help you configure these settings. However, you can configure it manually:

    ```bash
    cp .env.example .env
    ```

    **Key Variables:**
    - `DATABASE_URL`: Connection string (e.g., `postgresql://postgres:postgres@localhost:5433/personal_guru`).
    - `PORT`: Default `5011`.
    - `LLM_BASE_URL`:
      - **Ollama**: `http://localhost:11434/v1`
      - **LMStudio**: `http://localhost:1234/v1`
      - **OpenAI**: `https://api.openai.com/v1`
      - **Gemini**: `https://generativelanguage.googleapis.com/v1beta/openai/`
    - `LLM_MODEL_NAME`: e.g., `llama3`, `gpt-4o`.
    - `TTS_BASE_URL`: `http://localhost:8969/v1` (Replace `localhost` with your machine's actual LAN IP address if running on another machine).
    - `STT_BASE_URL`: `http://localhost:8969/v1` (Same as TTS if using Speaches).

4. **Database Setup (Docker)**:
    Start the Postgres database using Docker:

    ```bash
    docker compose up -d db
    ```

    *Starts PostgreSQL on `localhost:5433`.*
5. **Start the Speech Server (TTS & STT)**:

    ```bash
    docker compose up -d speaches
    ```

    *Starts Speaches on `localhost:8969`.*

    Download the models inside the container (Wait a few seconds for the container to start):

    ```bash
    # TTS Model
    docker compose exec speaches uv tool run speaches-cli model download speaches-ai/Kokoro-82M-v1.0-ONNX

    # STT Model
    docker compose exec speaches uv tool run speaches-cli model download Systran/faster-whisper-medium.en
    ```

    **Test TTS:**

    ```bash
    curl "http://localhost:8969/v1/audio/speech" -s -H "Content-Type: application/json" \
      --output test.mp3 \
      --data '{
        "input": "Hello! This is a test of local text to speech.",
        "model": "speaches-ai/Kokoro-82M-v1.0-ONNX",
        "voice": "af_bella",
        "speed": 1.0
      }'
    ```

    **Test STT:**

    ```bash
    curl "http://localhost:8969/v1/audio/transcriptions" \
      -F "file=@test.mp3" \
      -F "model=Systran/faster-whisper-medium.en" \
      -F "vad_filter=true" \
      -F "temperature=0"
    ```

6. **Init Database**:

    ```bash
    python scripts/update_database.py
    ```

7. **Run**:

    ```bash
    python run.py
    ```

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
    System_Ext(speaches, "Speaches (Kokoro)", "OpenAI-compatible TTS server.")

    Rel(user, personal_guru, "Uses", "HTTPS")
    Rel(personal_guru, openai, "Generates Content via", "API")
    Rel(personal_guru, youtube, "Search & Embeds", "API")
    Rel(personal_guru, speaches, "Generates Audio via", "API")
```

See [docs/architecture.md](docs/architecture.md) for Container, Component, and Sequence diagrams.

## Database Schema

The application uses the following PostgreSQL tables:

- **users**: Stores user accounts and profiles.
- **topics**: Main table for each subject the user is learning.
- **study_steps**: Steps within a study plan (one-to-many from topics).
- **quizzes**: Quizzes generated for a topic.
- **flashcards**: Flashcards for vocabulary terms.
- **chat_sessions**: Stores the conversational history for "Chat Mode" (one-to-one with topics). Note: "Chapter Mode" side-chats are stored directly in `study_steps.chat_history`.

## Database Migration (Recommended Safe Method)

If you plan to move data between different types of computers (e.g., your Linux server to a Windows laptop), it is safer to use the built-in backup tools:

1. **Export (on old machine):**

   ```bash
   docker compose exec db pg_dump -U postgres personal_guru > backup.sql
   ```

2. **Import (on new machine):**
   Move the `backup.sql` file to the new machine, start the fresh empty container, and run:

   ```bash
   # Copy file into container
   docker cp backup.sql personal-guru-db-1:/backup.sql

   # Restore
   docker compose exec db psql -U postgres -d personal_guru -f /backup.sql
   ```

## Enabling HTTPS for Microphone Access, reels and other security features

Modern web browsers require a secure (HTTPS) connection to allow web pages to access the microphone, and to enable reels mode.

### Method A: Self-Signed Certificate (for Local Development)

This is the simplest way to enable HTTPS for local testing.

1. **Generate the Certificate:**
    The repository includes a script to generate a self-signed certificate.

    ```bash
    python scripts/generate_cert.py
    ```

    This will create a `certs` directory with `cert.pem` and `key.pem` files.

2. **Run the Application:**
    Start Personal-Guru as you normally would. The Flask server will automatically detect the certificate and start with HTTPS.

3. **Trust the Certificate in Your Browser:**
    When you navigate to `https://localhost:5002`, your browser will show a privacy warning. You must accept the risk to proceed.

### Method B: Reverse Proxy (for Production)

Using a reverse proxy like Nginx or Caddy is the standard way to handle HTTPS in a production environment. The reverse proxy manages the SSL certificates (e.g., from Let's Encrypt) and forwards traffic to the Personal-Guru application, which can run on standard HTTP.

**General Steps:**

1. **Run Personal-Guru:** Start the Personal-Guru application on its default port (`5002`) without any SSL context.
2. **Set Up Reverse Proxy:**
    - Configure your reverse proxy (e.g., Nginx Proxy Manager, Caddy) to create a new proxy host.
    - **Domain:** Your public domain (e.g., `personal-guru.your-domain.com`).
    - **Scheme:** `http`.
    - **Forward Hostname/IP:** The IP address of the machine running Personal-Guru.
    - **Forward Port:** `5002`.
    - **Enable WebSocket Support:** This is critical for the voice communication to work.
3. **Enable SSL:**
    - In your reverse proxy's SSL settings, request a new SSL certificate (e.g., using Let's Encrypt).
    - Enable "Force SSL" and "HTTP/2 Support".

After saving, you can access Personal-Guru securely at your public domain.

## Project & Community

- **[Contributing](CONTRIBUTING.md)**: Learn how to set up the dev environment and submit PRs.
- **[Security Policy](SECURITY.md)**: Read about how we handle security and report vulnerabilities.
- **[License](LICENSE)**: Released under the AGPL-3.0 License.

## Utility Scripts for Developers

The `scripts/` folder contains several utility scripts to assist with development, database management, and visualization.

### Database Tools

- **`scripts/generate_dbml.py`**
  - **Purpose:** Generates a DBML (Database Markup Language) file from your SQLAlchemy models.
  - **Usage:** `python scripts/generate_dbml.py > schema.dbml`
  - **Use Case:** Copy the output to [dbdiagram.io](https://dbdiagram.io) to visualize and interactively edit your schema.

- **`scripts/visualize_db.py`**
  - **Purpose:** Generates a Mermaid.js Entity Relationship Diagram (ERD).
  - **Usage:** `python scripts/visualize_db.py`
  - **Use Case:** Copy the output into a Markdown file (like `docs/schema.md`) to view the diagram directly in GitHub or compatible editors.

- **`scripts/db_viewer.py`**
  - **Purpose:** Launches a visual web interface (Flask-Admin) to browse and manage database records.
  - **Usage:** `python scripts/db_viewer.py`
  - **URL:** Open `http://localhost:5012` to view tables.

- **`scripts/update_database.py`**
  - **Purpose:** Initializes tables and performs safe migrations (adding new columns/tables).
  - **Usage:** `python scripts/update_database.py`

### Other Utilities

- **`scripts/generate_cert.py`**
  - **Purpose:** Generates self-signed SSL certificates (`cert.pem`, `key.pem`) for local HTTPS development (required for microphone access).
  - **Usage:** `python scripts/generate_cert.py`

## For Developers: API Documentation

You can access the interactive API documentation (Swagger UI) at **http://localhost:5011/apidocs/#/** to explore endpoints and test requests.

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

## For Developers: Pre-commit Hooks

This project uses `pre-commit` to ensure code quality (linting, formatting, checking for merge conflicts, etc.) before every commit.

### Installation

1. **Install the hooks:**

    ```bash
    pre-commit install
    ```

2. **Run manually (optional):**
    To run the hooks on all files without committing:

    ```bash
    pre-commit run --all-files
    ```

### Hooks Included

- **Trailing Whitespace**: Removes trailing whitespace.
- **Merge Conflicts**: Checks for unresolved merge conflict markers.
- **Black**: Formats Python code.
- **Ruff**: Lints Python code.
- **Prettier**: Formats JS, CSS, and HTML.
- **Codespell**: Checks for spelling errors.
- **Interrogate**: Checks for missing docstrings in Python code.
