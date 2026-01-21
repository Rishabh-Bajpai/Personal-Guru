import os


class Config:
    """Application configuration settings loaded from environment variables."""

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Server-side sessions: LLM responses exceed the 4KB cookie limit,
    # so we store session data on the filesystem instead
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_session')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True

    # External APIs
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL')
    TTS_BASE_URL = os.environ.get('TTS_BASE_URL')
    STT_BASE_URL = os.environ.get('STT_BASE_URL')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

    # App Settings
    USER_BACKGROUND = os.environ.get('USER_BACKGROUND', 'a beginner')
    ENABLE_TELEMETRY_LOGGING = os.environ.get('ENABLE_TELEMETRY_LOGGING', 'True').lower() == 'true'
    SANDBOX_PATH = os.environ.get('SANDBOX_PATH') or os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'sandbox')
