# Personal Guru - Windows Installation & Build Guide

## 📦 What is included?
The `PersonalGuru.exe` is a standalone executable for Windows 10/11 (64-bit).

It bundles:
*   **The Application Code**: Core logic, web interface, and agents.
*   **Python Dependencies**: Flask, SQLAlchemy, WeasyPrint, etc.
*   **Local AI Models** (optional): Kokoro TTS, Faster Whisper STT.

## 🛠️ User Requirements
The executable **does not** contain the database or AI models. Before running the application, the user must set up:

1.  **Ollama** (Required for AI features):
    *   Download and install from [ollama.com](https://ollama.com).
    *   Must be running (default `http://localhost:11434`).
    *   Pull required models (e.g., `ollama pull llama3`, `ollama pull mistral`).
2.  **API Keys** (Optional but recommended):
    *   OpenAI API Key (for GPT-based agents).
    *   YouTube Data API Key (for Reel mode).

> **Note**: On first launch, the Setup Wizard will open in your browser to help you configure these connections.

---

## 🚀 How to Run (End User)
1.  **Download** the `PersonalGuru.exe` from the releases.
2.  **Place it in a dedicated folder** (the app will create `site.db` and `data/` in the same directory).
3.  **Double-click** `PersonalGuru.exe` to run.
4.  The application will start, and your default web browser will open automatically at `http://127.0.0.1:5011`.

### First Run
*   If configuration is not set, the **Setup Wizard** will guide you through the initial configuration.
*   Enter your Ollama URL, API keys, and other settings.
*   After completing the wizard, the application will restart automatically.

---

## 🏗️ How to Build (For Developers)

### Prerequisites
*   **Conda** (Miniconda or Anaconda) - for managing Python environments.
*   **Python 3.11** - required for compatibility with `av`, `spacy`, and other native dependencies.
*   **Git** - for cloning the repository.

### Step 1: Create Conda Environment
Create a dedicated Python 3.11 environment:
```powershell
conda create -n personal_guru_py311 python=3.11 -y
conda activate personal_guru_py311
```

### Step 2: Clone the Repository
```powershell
git clone https://github.com/yourusername/Personal-Guru.git
cd Personal-Guru
```

### Step 3: Build the Executable
> ⚠️ **IMPORTANT**: Make sure you have activated the `personal_guru_py311` conda environment before running the build script!

Run the build script from PowerShell:
```powershell
# Activate the conda environment first
conda activate personal_guru_py311

# Run the build script
.\scripts\installation\windows\build_exe.ps1
```

For a **clean build** (recommended if you encounter issues):
```powershell
.\scripts\installation\windows\build_exe.ps1 -Clean
```

### Build Output
The final artifact will be placed in the `dist/` folder:
```
dist/PersonalGuru.exe
```

---

## 🔧 Troubleshooting Build

### "Failed to collect submodules" with Python version mismatch
**Symptoms**: Errors mentioning `.cp311` or `.cp313` version mismatches, or messages like:
```
numpy C-extensions failed... incompatible with python 'cpython-313'
```

**Solution**: You likely have the wrong Python version active. Ensure you activate the correct conda environment:
```powershell
conda activate personal_guru_py311
.\scripts\installation\windows\build_exe.ps1 -Clean
```

### "ModuleNotFoundError" during build
**Symptoms**: Errors like `No module named '_cffi_backend'` or `No module named 'pydantic_core._pydantic_core'`.

**Solution**: Your `.build_venv` is corrupted. Run a clean build:
```powershell
.\scripts\installation\windows\build_exe.ps1 -Clean
```

### "PyInstaller failed with exit code 1"
**Symptoms**: Build fails with various errors in the PyInstaller step.

**Solution**: 
1.  Check that the correct conda environment is activated.
2.  Run with `-Clean` flag to rebuild everything from scratch.
3.  Check the error logs for specific missing modules.

### WeasyPrint Warning on Startup
**Symptom**: Warning message: `WeasyPrint not available (PDF export disabled): cannot load library 'libgobject-2.0-0'`

**Note**: This is expected on Windows. WeasyPrint requires GTK+ libraries which are complex to bundle. PDF export will be disabled, but all other features work normally.

---

## 📁 Runtime Files
When running `PersonalGuru.exe`, the following files/folders are created in the same directory:

| File/Folder | Description |
|-------------|-------------|
| `site.db` | SQLite database storing user data, settings, and content |
| `data/` | Application data directory |
| `data/sandbox/` | Temporary files for document processing |
| `data/flask_session/` | Server-side session storage |
| `.env` | Configuration file (created by Setup Wizard) |

---

## 🔐 Optional: SSL/HTTPS
To enable HTTPS:
1.  Create a `certs/` folder next to the executable.
2.  Place your SSL certificates:
    *   `certs/cert.pem`
    *   `certs/key.pem`
3.  Restart the application. It will automatically detect and use HTTPS.
