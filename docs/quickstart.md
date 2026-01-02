# Quick Start Guide

## Prerequisites

- **Python 3.10+** (We recommend [Miniconda](https://docs.conda.io/en/latest/miniconda.html))
- **Docker** (For the database)

## Automatic Setup (Recommended)

We provide a simple script to get everything up and running in minutes.

1.  **Run the setup script:**
    - **Linux/Mac**:
      ```bash
      ./setup.sh
      ```
    - **Windows**:
      ```cmd
      setup.bat
      ```
    This script will:
    - Create a Conda environment called `Personal-Guru`.
    - Install all dependencies.
    - Start the database container.
    - Initialize the database tables.

2.  **Activate the Environment:**
    ```bash
    conda activate Personal-Guru
    ```

3.  **Run the Application:**
    ```bash
    python run.py
    ```

4.  **Configure:**
    On the first run, your browser will open a **Setup Wizard** where you can enter your LLM details.

## Docker Quick Start

If you prefer to run everything in containers:

```bash
docker compose up --build
```

The app will be available at `http://localhost:5011`.
