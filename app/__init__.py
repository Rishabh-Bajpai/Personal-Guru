from flask import Flask, request, redirect, url_for
from config import Config
from .common.extensions import db, migrate
from flask_wtf.csrf import CSRFProtect
from flask_session import Session  # Server-side sessions for large chat histories

csrf = CSRFProtect()
sess = Session()

from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = 'main.login'

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='common/templates')
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    sess.init_app(app)  # Initialize server-side sessions
    login_manager.init_app(app)

    from app.common.models import User
    @login_manager.user_loader
    def load_user(username):
        return User.query.get(username)

    # Register Blueprints
    from app.modes.chapter import chapter_bp
    from app.modes.quiz import quiz_bp
    from app.modes.flashcard import flashcard_bp
    from app.modes.reel import reel_bp
    from app.modes.chat import chat_bp
    
    app.register_blueprint(chapter_bp, url_prefix='/chapter')
    app.register_blueprint(quiz_bp, url_prefix='/quiz')
    app.register_blueprint(flashcard_bp, url_prefix='/flashcards')
    app.register_blueprint(reel_bp, url_prefix='/reels')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    
    # Global Routes (Home, Background, etc.)
    from app.core import storage # legacy storage
    
    from .common.routes import main_bp
    app.register_blueprint(main_bp)

    @app.before_request
    def require_login():
        from flask_login import current_user
        if not current_user.is_authenticated:
            # List of endpoints accessible without login
            # 'main.login', 'main.signup', 'static'
            if request.endpoint and request.endpoint not in ['main.login', 'main.signup', 'static'] and not request.endpoint.startswith('static'):
                 return redirect(url_for('main.login'))

    return app
