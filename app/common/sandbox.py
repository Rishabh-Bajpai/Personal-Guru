import os
import subprocess
import shutil
import uuid
import sys
import base64
import glob
import logging
from config import Config

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Ensure a handler exists to output to stderr/stdout if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


SHARED_SANDBOX_ID = "shared_env"


def cleanup_old_sandboxes(base_path=None):
    """Removes the entire sandbox directory to clean up old sessions, except the shared env."""
    if base_path is None:
        base_path = Config.SANDBOX_PATH

    if os.path.exists(base_path):
        try:
            logger.info(f"Cleaning up old sandboxes at: {base_path}")
            # Iterate over items in the base_path
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                # Skip the shared environment
                if item == SHARED_SANDBOX_ID:
                    logger.info(f"Skipping cleanup for shared sandbox: {item}")
                    continue
                
                if os.path.isdir(item_path):
                    try:
                        shutil.rmtree(item_path)
                        logger.info(f"Removed sandbox: {item}")
                    except Exception as e:
                        logger.error(f"Failed to remove sandbox {item}: {e}")
            logger.info("Sandbox cleanup complete.")
        except Exception as e:
            logger.error(f"Failed to clean up sandbox directory: {e}")


class Sandbox:
    """Isolated Python execution environment for running untrusted code."""

    def __init__(
            self,
            base_path=None,
            sandbox_id=None):
        if base_path:
            self.base_path = base_path
        else:
            try:
                from flask import current_app
                if current_app:
                    self.base_path = current_app.config.get('SANDBOX_PATH', Config.SANDBOX_PATH)
                else:
                    self.base_path = Config.SANDBOX_PATH
            except ImportError:
                 self.base_path = Config.SANDBOX_PATH

        self.id = sandbox_id if sandbox_id else str(uuid.uuid4())
        self.path = os.path.join(self.base_path, self.id)
        self.venv_path = os.path.join(self.path, "venv")

        if sandbox_id and os.path.exists(self.venv_path):
            logger.info(f"Resuming existing sandbox: {self.id}")
        else:
            logger.info(f"Initializing sandbox: {self.id} at {self.path}")
            self._setup()

    def _setup(self):
        """Creates the sandbox directory and virtual environment."""
        if os.path.exists(self.venv_path):
            return

        os.makedirs(self.path, exist_ok=True)
        
        # Find the Python executable to use for creating venv
        python_exe = self._find_python_executable()
        if not python_exe:
            logger.error("No Python interpreter found. Code execution sandbox will not work.")
            logger.error("Please ensure Python is installed and in PATH.")
            # Create a marker file to indicate venv creation failed
            with open(os.path.join(self.path, ".no_python"), "w") as f:
                f.write("No Python interpreter found for sandbox creation")
            return
        
        # Create venv
        logger.info(f"Creating virtual environment in {self.venv_path} using {python_exe}...")
        try:
            subprocess.run([python_exe, "-m", "venv", self.venv_path], check=True)
            logger.info("Virtual environment created.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create virtual environment: {e}")
            with open(os.path.join(self.path, ".venv_failed"), "w") as f:
                f.write(f"Failed to create venv: {e}")

    def _find_python_executable(self):
        """
        Find a suitable Python executable for creating virtual environments.
        
        In frozen mode (PyInstaller), sys.executable points to the .exe itself,
        so we need to find the system Python installation.
        
        Returns:
            str: Path to Python executable, or None if not found.
        """
        # If not frozen, use sys.executable (normal development mode)
        if not getattr(sys, 'frozen', False):
            return sys.executable
        
        logger.info("Frozen mode detected. Searching for system Python...")
        
        # Try common Python executable names via PATH
        python_names = ['python', 'python3', 'python3.11', 'python3.12', 'python3.13']
        for name in python_names:
            python_path = shutil.which(name)
            if python_path:
                # Verify it's not pointing back to our frozen exe
                if python_path.lower() != sys.executable.lower():
                    logger.info(f"Found system Python: {python_path}")
                    return python_path
        
        # Try common Windows Python installation paths
        if os.name == 'nt':
            common_paths = [
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\Python\Python313\python.exe'),
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\Python\Python312\python.exe'),
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\Python\Python311\python.exe'),
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\Python\Python310\python.exe'),
                r'C:\Python313\python.exe',
                r'C:\Python312\python.exe',
                r'C:\Python311\python.exe',
                r'C:\Python310\python.exe',
            ]
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"Found system Python: {path}")
                    return path
        
        logger.warning("No system Python interpreter found.")
        return None

    def install_deps(self, libraries):
        """Installs dependencies in the virtual environment."""
        if not libraries:
            return

        logger.info(f"Installing dependencies: {libraries}...")
        if os.name == 'nt':
            pip_path = os.path.join(self.venv_path, "Scripts", "pip")
        else:
            pip_path = os.path.join(self.venv_path, "bin", "pip")

        try:
            subprocess.run([pip_path, "install"] + libraries,
                           check=True, cwd=self.path, capture_output=True)
            logger.info("Dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode()
            logger.error(f"Error installing dependencies: {error_msg}")
            return f"Error installing dependencies: {error_msg}"

    def run_code(self, code):
        """Runs the provided code in the sandbox."""
        logger.info("Preparing to run code...")
        script_path = os.path.join(self.path, "script.py")
        with open(script_path, "w") as f:
            f.write(code)

        if os.name == 'nt':
            python_path = os.path.join(self.venv_path, "Scripts", "python")
        else:
            python_path = os.path.join(self.venv_path, "bin", "python")

        try:
            logger.info(f"Executing script: {script_path}")
            result = subprocess.run(
                [python_path, "script.py"],
                cwd=self.path,
                capture_output=True,
                check=False,  # We handle errors in the output
                timeout=30  # 30s timeout
            )
            output = result.stdout.decode()
            error = result.stderr.decode()
            logger.info("Execution completed.")
        except subprocess.TimeoutExpired:
            output = ""
            error = "Execution timed out."
            logger.error("Execution timed out.")
        except Exception as e:
            output = ""
            error = str(e)
            logger.error(f"Execution failed: {e}")

        # Collect images
        images = []
        for img_path in glob.glob(os.path.join(self.path, "*.png")):
            with open(img_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
                images.append(img_data)

        if images:
            logger.info(f"Captured {len(images)} images.")

        return {
            "output": output,
            "error": error,
            "images": images
        }

    def cleanup(self):
        """Removes the sandbox directory."""
        if os.path.exists(self.path):
            logger.info(f"Cleaning up sandbox: {self.path}")
            shutil.rmtree(self.path)
