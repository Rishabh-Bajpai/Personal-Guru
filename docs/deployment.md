# Deployment Guide

## Self-Hosting (Local)

The easiest way to self-host is using the provided `setup.sh` script or Docker Compose.

### Option 1: Hybrid (Local Python + Docker DB)
This is best for development or if you want to use local hardware (GPU) natively for the LLM.

1.  Run `./setup.sh`
2.  Updates/Dev: `pip install -r requirements/dev.txt`

### Option 2: Full Docker
Run `docker compose up -d`. This runs the Web App and the Database in containers.
Note: To access a local LLM (like Ollama) from inside the container, use `http://host.docker.internal:11434`.

## LLM Configuration

You can configure the LLM provider in the `.env` file or via the Setup Wizard.

- **Ollama**: `http://localhost:11434/v1` (Native) or `http://host.docker.internal:11434/v1` (Docker)
- **LMStudio**: `http://localhost:1234/v1`
- **OpenAI**: `https://api.openai.com/v1`

## Production Deployment

For production, we recommend using a reverse proxy for HTTPS.

1.  **Export Dependencies**:
    The production dependencies are in `requirements/prod.txt`.

2.  **WSGI Server**:
    Use `gunicorn` to run the application:
    ```bash
    gunicorn -w 4 -b 0.0.0.0:5011 run:app
    ```
