# Personalized Learning AI App

This is a Flask-based web application that serves as a proof-of-concept for a personalized learning tool. It uses a multi-agent AI system to create an interactive learning experience tailored to the user's chosen topic.

## Features

- **Dynamic Study Plans:** Enter any topic and receive a custom, step-by-step study plan.
- **Detailed Study Content:** Each step in the study plan now includes detailed content.
- **Interactive Learning:** Progress through the plan one step at a time.
- **Text-to-Speech:** Listen to each learning step with integrated TTS audio.
- **Knowledge Assessment:** Answer multiple-choice questions after each step to test your understanding.
- **Adaptive Learning:** The study plan adapts to your performance on the "Check Your Understanding" questions.
- **Q&A Chat:** Ask questions about the study material and get answers from an AI assistant.
- **Instant Feedback:** Receive immediate feedback on your answers.
- **Local AI Integration:** Designed to connect with locally-hosted AI services (LLM, TTS) for privacy and control.
- **Export to Markdown:** At the end of a course, you can export the entire study plan and content to a markdown file, perfect for importing into note-taking apps like Notion, Obsidian, or NotebookLM.
- **Comprehensive Test Suite:** Includes a full suite of unit tests to verify application logic.

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

Now, open the `.env` file and customize the settings for your environment. You will need to provide the URLs for your Ollama and TTS services.

## Running the Application

To run the application, you need to have three components running: the Ollama LLM server, the Coqui TTS server (optional), and the main Flask application.

### 1. Ollama (LLM Server)

Ensure your Ollama instance is running and accessible over the network. If you are running Ollama in Docker, make sure to expose its port (default 11434).

You can install Ollama from the official website: [https://ollama.com/](https://ollama.com/)

For GPU support with Docker, you can run Ollama using the following command:

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
