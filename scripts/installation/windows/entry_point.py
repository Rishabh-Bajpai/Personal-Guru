import os
import sys
import multiprocessing
from dotenv import load_dotenv

# Fix for multiprocessing (needed for some libraries and updates)
multiprocessing.freeze_support()

def get_base_dir():
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # If the application is run from a Python interpreter
        # Logic: This file is in scripts/installation/windows/entry_point.py
        # We need to go up 3 levels to get to the project root
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

base_dir = get_base_dir()

# Ensure we have a data directory for persistent storage
data_dir = os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

# Set environment variables for persistence before importing config
# These will override the defaults in config.py which might point to temp dirs in frozen mode
if 'DATABASE_URL' not in os.environ:
    db_path = os.path.join(base_dir, 'site.db')
    os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"

if 'SANDBOX_PATH' not in os.environ:
    os.environ['SANDBOX_PATH'] = os.path.join(data_dir, 'sandbox')

# Determine where to look for .env
# In frozen mode, we look next to the exe
env_path = os.path.join(base_dir, '.env')
load_dotenv(env_path, override=True)

# In frozen mode, default to native TTS/STT (bundled Kokoro/Whisper)
# This is set AFTER loading .env so we can override invalid values
if getattr(sys, 'frozen', False):
    # Valid providers are 'native' or 'externalapi'
    # Default to externalapi for TTS as native option is removed, but native for STT
    tts_provider = os.environ.get('TTS_PROVIDER', 'externalapi').lower()
    stt_provider = os.environ.get('STT_PROVIDER', 'native').lower()
    
    # Enforce externalapi for TTS
    if tts_provider != 'externalapi':
        os.environ['TTS_PROVIDER'] = 'externalapi'
        
    # STT can technically still be native (Whisper) if not removed, but user context implies cleaning up "local TTS (Kokoro)".
    # I will stick to TTS enforcement primarily, but if the user wants to remove "local TTS from configuration", I should ensure it's not selected.


# Now import app modules
# We need to make sure the root directory is in sys.path if running from script
if not getattr(sys, 'frozen', False):
    sys.path.append(base_dir)
else:
    # In frozen mode, PyInstaller bundles data files into a temp directory (_MEIPASS)
    # We need to add that to sys.path so Python can find 'config' and 'app' modules
    bundle_dir = getattr(sys, '_MEIPASS', base_dir)
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

from app.common.config_validator import validate_config
from config import Config

# Patch Config for Session directory if running frozen
# (config.py sets this based on __file__ which is temp in frozen mode)
if getattr(sys, 'frozen', False):
    session_dir = os.path.join(data_dir, 'flask_session')
    Config.SESSION_FILE_DIR = session_dir
    os.makedirs(session_dir, exist_ok=True)

def main():
    try:
        # Check configuration
        missing_vars = validate_config()

        if missing_vars:
            print(f"Missing configuration variables: {missing_vars}. Starting Setup Wizard...")
            from app.setup_app import create_setup_app
            app = create_setup_app()
        else:
            from app import create_app
            from app.common.sandbox import cleanup_old_sandboxes
            # Cleanup old sandboxes on startup
            cleanup_old_sandboxes()
            app = create_app()
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR: Failed to initialize application")
        print(f"{'='*60}")
        print(f"Details: {e}")
        print(f"\nPlease check that all files are present and try again.")
        print(f"If this persists, please report the issue.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    port = int(os.getenv('PORT', 5011))
    
    # Certs relative to base_dir
    cert_path = os.path.join(base_dir, 'certs', 'cert.pem')
    key_path = os.path.join(base_dir, 'certs', 'key.pem')

    ssl_context = None
    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"SSL Certificates found. Enabling HTTPS on port {port}.")
        ssl_context = (cert_path, key_path)
    else:
        print(f"No SSL Certificates found. Running on HTTP port {port}.")

    # In frozen mode, we typically don't want the reloader as it spawns new processes
    # which can be tricky with PyInstaller (require fork/exec logic)
    # We disable debug and reloader for the stable release exe
    use_reloader = False if getattr(sys, 'frozen', False) else True
    debug_mode = False if getattr(sys, 'frozen', False) else True
    
    # If user explicitly asks for debug via env
    if os.getenv('FLASK_DEBUG'):
        debug_mode = True

    print(f"Starting server on port {port}...")

    def open_browser(port):
        """Wait for the server to start and then open the browser."""
        import time
        import webbrowser
        time.sleep(1.5)
        url = f'http://127.0.0.1:{port}'
        print(f"Opening browser at {url}")
        webbrowser.open(url)

    # Start browser in a separate thread, but only if not already opened
    # This prevents duplicate tabs when Flask restarts
    if os.environ.get('PG_BROWSER_OPENED') != '1':
        os.environ['PG_BROWSER_OPENED'] = '1'
        import threading
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    else:
        print("Browser already opened in previous run, skipping.")
    
    app.run(
        debug=debug_mode,
        host='127.0.0.1',
        port=port,
        use_reloader=use_reloader,
        ssl_context=ssl_context
    )

if __name__ == '__main__':
    main()
