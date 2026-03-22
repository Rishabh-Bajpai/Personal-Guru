import os
import tempfile
from dotenv import load_dotenv

def load_environment_variables():
    """
    Load environment variables from .env file and handle Docker-specific overrides.

    This function:
    1. Captures critical Docker-injected variables.
    2. Loads the .env file (overriding Docker vars).
    3. Restores specific Docker variables if they are valid internal service URLs.
    """
    # --- Robust Environment Loading for Docker/Windows ---
    # 1. Capture critical variables injected by Docker (which are correct for internal networking)
    docker_db_url = os.environ.get('DATABASE_URL')
    docker_tts_url = os.environ.get('TTS_BASE_URL')
    docker_stt_url = os.environ.get('STT_BASE_URL')
    docker_tts_provider = os.environ.get('TTS_PROVIDER')
    docker_stt_provider = os.environ.get('STT_PROVIDER')

    # 2. Force-load .env to get the latest user configuration (overriding stale Docker vars)
    load_dotenv(override=True)

    # 3. Restore critical Docker variables if they were valid internal services
    # This prevents local .env values (like sqlite:/// or localhost) from breaking the container.
    if docker_db_url and 'postgres' in docker_db_url:
        os.environ['DATABASE_URL'] = docker_db_url

    if docker_tts_url and 'speaches' in docker_tts_url:
        os.environ['TTS_BASE_URL'] = docker_tts_url

    if docker_stt_url and 'speaches' in docker_stt_url:
        os.environ['STT_BASE_URL'] = docker_stt_url

    # Restore providers if they were set (usually 'externalapi' in Docker)
    if docker_tts_provider == 'externalapi':
        os.environ['TTS_PROVIDER'] = docker_tts_provider

    if docker_stt_provider == 'externalapi':
        os.environ['STT_PROVIDER'] = docker_stt_provider




class Config:
    """Application configuration settings loaded from environment variables."""

    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Server-side sessions: LLM responses exceed the 4KB cookie limit,
    # so we store session data on the filesystem instead
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.environ.get('SESSION_FILE_DIR') or os.path.join(tempfile.gettempdir(), f'personal-guru-flask-session-{os.getuid()}')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True

    # External APIs
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL')
    TTS_BASE_URL = os.environ.get('TTS_BASE_URL')
    STT_BASE_URL = os.environ.get('STT_BASE_URL')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    TTS_PROVIDER = os.environ.get('TTS_PROVIDER', 'externalapi')  # Options: 'native', 'externalapi'
    STT_PROVIDER = os.environ.get('STT_PROVIDER', 'externalapi')  # Options: 'native', 'externalapi'

    # ComfyUI (Book Cover Generation)
    COMFYUI_SERVER_ADDRESS = os.environ.get('COMFYUI_SERVER_ADDRESS', 'localhost:8188')
    COMFYUI_WORKFLOW_PATH = os.environ.get('COMFYUI_WORKFLOW_PATH', os.path.join(os.path.abspath(os.path.dirname(__file__)), 'scripts', 'example_workflow.json'))

    # App Settings
    USER_BACKGROUND = os.environ.get('USER_BACKGROUND', 'a beginner')
    ENABLE_TELEMETRY = os.environ.get('ENABLE_TELEMETRY', 'True').lower() == 'true'
    ENABLE_TELEMETRY_LOGGING = os.environ.get('ENABLE_TELEMETRY_LOGGING', 'True').lower() == 'true'
    SANDBOX_PATH = os.environ.get('SANDBOX_PATH') or os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'sandbox')

class TestConfig(Config):
    """Configuration for running tests."""
    TESTING = True
    SECRET_KEY = 'test-secret-key-for-unit-tests'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
