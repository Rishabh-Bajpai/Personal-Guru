from flask import Flask, render_template, request, session, redirect, url_for
from config import Config
from .common.extensions import db, migrate

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='common/templates')
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register Blueprints
    from app.modes.chapter import chapter_bp
    from app.modes.quiz import quiz_bp
    from app.modes.flashcard import flashcard_bp
    from app.modes.reel import reel_bp
    from app.modes.chat import chat_bp
    
    app.register_blueprint(chapter_bp)
    app.register_blueprint(quiz_bp, url_prefix='/quiz')
    app.register_blueprint(flashcard_bp, url_prefix='/flashcards')
    app.register_blueprint(reel_bp)
    app.register_blueprint(chat_bp, url_prefix='/chat')
    
    # Global Routes (Home, Background, etc.)
    # We can define them here or move to a 'main' blueprint. 
    # For now, defining here to match the requested structure which implies simple root.
    
    from app.core import storage # legacy storage
    
    from .common.routes import main_bp
    app.register_blueprint(main_bp)

    return app
