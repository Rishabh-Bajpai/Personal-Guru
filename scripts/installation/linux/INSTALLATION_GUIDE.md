# Personal Guru - Linux Installation & Build Guide

## 📦 What is included?
The `PersonalGuru-x86_64.AppImage` is a standalone executable that works on most modern Linux distributions (Ubuntu 22.04 LTS and newer).

It bundles:
*   **The Application Code**: Core logic, web interface, and agents.
*   **Python Dependencies**: Flask, SQLAlchemy, WeasyPrint, etc.
*   **System Libraries**: Necessary drivers for PDF generation (Pango, Cairo).

## 🛠️ User Requirements
The AppImage **does not** contain the database or AI models. Before running the application, the user must look after:

1.  **PostgreSQL Database**:
    *   Must be running locally or defined in the config.
    *   **Extension Required**: `pgvector` must be installed and enabled on the database.
2.  **Ollama**:
    *   Must be running (default `http://localhost:11434`).
    *   Models should be pulled (e.g., `llama3`, `mistral`).
3.  **API Keys** (Optional but recommended):
    *   OpenAI API Key (for specific agents).
    *   YouTube Data API Key (Reel mode).

> **Note**: On first launch, the Setup Wizard will open in your browser to help you configure these connections.

---

## 🚀 How to Run (End User)
1.  **Download** the `PersonalGuru-x86_64.AppImage`.
2.  **Make it executable**:
    ```bash
    chmod +x PersonalGuru-x86_64.AppImage
    ```
3.  **Run it**:
    ```bash
    ./PersonalGuru-x86_64.AppImage
    ```
4.  The application will start, and your default web browser will open automatically.

---

## 🏗️ How to Build (For Developers)
To create the release-ready AppImage, use the Docker-based build script. This ensures compatibility with older Linux versions (Ubuntu 22.04+).

### Prerequisites
*   Docker installed and running.

### Build Command
Run this from the project root:
```bash
./scripts/installation/linux/build_with_docker.sh
```

### Build output
The final artifact will be placed in your local `dist/` folder:
`dist/PersonalGuru-x86_64.AppImage`

### Troubleshooting Build
*   **"pip: command not found" or "ModuleNotFoundError: No module named 'pip'"**: Re-run the build. The script automatically recreates the virtual environment to fix Python version mismatches (e.g., between Python 3.13 and 3.11).
*   **"subprocess-exited-with-error" for `av` or `spacy`**: These libraries require system dependencies (`ffmpeg` dev libs, `pkg-config`) and Python 3.11. The provided `Dockerfile` handles this. stick to `build_with_docker.sh`.
*   **"struct.error: 'I' format requires 0 <= number <= 4294967295"**: This means the single-file executable exceeded 4GB. The scripts now use `--onedir` mode to avoid this limit.
*   **"OSError: cannot load library libpango"**: Ensure `Dockerfile` installs `libpango-1.0-0` and `build_linux.sh` uses `--collect-all weasyprint`.
