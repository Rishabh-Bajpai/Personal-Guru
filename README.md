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
- **Comprehensive Test Suite:** Includes a full suite of unit tests to verify application logic.

## Getting Started

Follow these instructions to get the application running on your local machine.

### Prerequisites

- Python 3.9+
- Access to a running instance of:
  - An Ollama-compatible LLM service.
  - A Coqui or Piper TTS service.

### 1. Setup Environment Variables

The application is configured using a `.env` file. Copy the example file and edit it with the URLs and models for your local AI services.

```bash
cp .env.example .env
```

Now, open the `.env` file and customize the settings for your environment.

### 2. Install Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 3. Run the Application

Once the dependencies are installed and your `.env` file is configured, you can start the Flask development server:

```bash
python app.py
```

The application will be available at `http://127.0.0.1:5001`.

### 4. Run the Tests

This project includes a comprehensive test suite that mocks the external AI services, allowing you to verify the application's internal logic without needing a live connection to them.

To run the tests, execute the following command in your terminal:

```bash
pytest
```
