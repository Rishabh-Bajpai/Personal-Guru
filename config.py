import os

class Config:
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
    LLM_ENDPOINT = os.environ.get('LLM_ENDPOINT')
    TTS_URL = os.environ.get('TTS_URL')
    
    # App Settings
    USER_BACKGROUND = os.environ.get('USER_BACKGROUND', 'a beginner')
