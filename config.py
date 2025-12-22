import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # External APIs
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_ENDPOINT = os.environ.get('LLM_ENDPOINT')
    TTS_URL = os.environ.get('TTS_URL')
    
    # App Settings
    USER_BACKGROUND = os.environ.get('USER_BACKGROUND', 'a beginner')
