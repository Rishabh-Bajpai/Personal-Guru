import os
import subprocess
import shutil
import uuid
import sys
import base64
import glob
import logging

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Ensure a handler exists to output to stderr/stdout if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


class Sandbox:
    """Isolated Python execution environment for running untrusted code."""

    def __init__(
            self,
            base_path="/tmp/personal_guru_sandbox",
            sandbox_id=None):
        self.id = sandbox_id if sandbox_id else str(uuid.uuid4())
        self.path = os.path.join(base_path, self.id)
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
        # Create venv
        logger.info(f"Creating virtual environment in {self.venv_path}...")
        subprocess.run([sys.executable, "-m", "venv",
                       self.venv_path], check=True)
        logger.info("Virtual environment created.")

    def install_deps(self, libraries):
        """Installs dependencies in the virtual environment."""
        if not libraries:
            return

        logger.info(f"Installing dependencies: {libraries}...")
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
