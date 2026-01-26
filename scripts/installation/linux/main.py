import sys
import os
import threading
import webbrowser
import time
from dotenv import load_dotenv

# Adjust paths if running as a PyInstaller bundle
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    # We may need to ensure implicit relative imports or path configurations work.
    # For now, we rely on standard imports.
    pass
else:
    # If running as a script from scripts/installation/linux/, add project root to sys.path
    # so we can import 'app'
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

from app.common.config_validator import validate_config  # noqa: E402

def open_browser(port):
    """Wait for the server to start and then open the browser."""
    time.sleep(1.5)
    url = f'http://127.0.0.1:{port}'
    print(f"Opening browser at {url}")
    webbrowser.open(url)

def main():
    # Check configuration
    missing_vars = validate_config()

    from config import Config

    class ProdConfig(Config):
        """Configuration for production AppImage environment."""
        # Use user's cache directory for writable data
        _app_name = "personal-guru"
        _user_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", _app_name)

        # Ensure directories exist
        os.makedirs(os.path.join(_user_cache_dir, "flask_session"), exist_ok=True)
        os.makedirs(os.path.join(_user_cache_dir, "sandbox"), exist_ok=True)

        SESSION_FILE_DIR = os.path.join(_user_cache_dir, "flask_session")
        SANDBOX_PATH = os.path.join(_user_cache_dir, "sandbox")

    app = None
    if missing_vars:
        print(f"Missing configuration variables: {missing_vars}. Starting Setup Wizard...")
        from app.setup_app import create_setup_app
        app = create_setup_app()
    else:
        from app import create_app
        from app.common.sandbox import cleanup_old_sandboxes
        # Cleanup old sandboxes on startup (use the writable path)
        cleanup_old_sandboxes(base_path=ProdConfig.SANDBOX_PATH)
        # Use ProdConfig to ensure writable paths
        app = create_app(config_class=ProdConfig)

    host = '127.0.0.1'
    # Use the port from environment or default to 5011
    port = int(os.getenv('PORT', 5011))

    # Start browser in a separate thread
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    print(f"Starting Personal Guru application on {host}:{port}")
    # Run Flask server
    # debug=False is important for production/binary use to avoid reloader issues
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
