from flask import Flask, request, redirect, url_for, jsonify, render_template
from config import Config
from .core.extensions import db, migrate
from flask_wtf.csrf import CSRFProtect
from flask_session import Session  # Server-side sessions for large chat histories
from flask_login import LoginManager
from flasgger import Swagger
import logging
import os
import secrets
import sys

csrf = CSRFProtect()
sess = Session()

login_manager = LoginManager()
login_manager.login_view = 'main.login'


def create_app(config_class=Config):
    """
    Application factory that creates and configures the Flask application.

    Args:
        config_class: Configuration class to use. Defaults to Config.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, template_folder='core/templates')
    app.config.from_object(config_class)

    live_secret_key = os.environ.get('SECRET_KEY') or app.config.get('SECRET_KEY')
    if not live_secret_key:
        live_secret_key = secrets.token_hex(32)
        logging.getLogger(__name__).warning(
            'SECRET_KEY was not set; using an ephemeral development key for this process.'
        )
    app.config['SECRET_KEY'] = live_secret_key

    # Register Custom Filters
    from app.common.utils import sanitize_html
    app.jinja_env.filters['sanitize_html'] = sanitize_html

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    sess.init_app(app)  # Initialize server-side sessions
    login_manager.init_app(app)

    # Create database tables if they don't exist
    # This is essential for first-run scenarios (especially from frozen .exe)
    with app.app_context():
        # Import models to register them with SQLAlchemy before create_all
        from app.core import models  # noqa: F401
        db.create_all()

    # Initialize Swagger
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec_1',
                "route": '/apispec_1.json',
                "rule_filter": lambda rule: True,  # all in
                "model_filter": lambda tag: True,  # all in
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/"
    }
    Swagger(app, config=swagger_config)

    # Initialize Telemetry Log Capture
    if app.config.get('ENABLE_TELEMETRY', True) and app.config.get('ENABLE_TELEMETRY_LOGGING', True) and not app.config.get('TESTING'):
        from app.common.log_capture import LogCapture
        LogCapture(app)

    from app.core.models import Login
    @login_manager.user_loader
    def load_user(userid):
        return Login.query.get(userid)

    # Register Blueprints
    from app.modes.chapter import chapter_bp
    from app.modes.quiz import quiz_bp
    from app.modes.flashcard import flashcard_bp
    from app.modes.reel import reel_bp
    from app.modes.chat import chat_bp
    from app.common import common_bp

    app.register_blueprint(chapter_bp, url_prefix='/chapter')
    app.register_blueprint(quiz_bp, url_prefix='/quiz')
    app.register_blueprint(flashcard_bp, url_prefix='/flashcards')
    app.register_blueprint(reel_bp, url_prefix='/reels')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(common_bp, url_prefix='/common')

    from app.modes.library import library_bp
    app.register_blueprint(library_bp, url_prefix='/library')

    # Global Routes (Home, Background, etc.)
    # Global Routes (Home, Background, etc.)

    from .core.routes import main_bp
    app.register_blueprint(main_bp)

    @app.before_request
    def require_login():
        from flask_login import current_user
        if not current_user.is_authenticated:
            # List of endpoints accessible without login
            # 'main.login', 'main.signup', 'static'
            if request.endpoint and request.endpoint not in [
                'main.login',
                'main.signup',
                'main.submit_feedback',
                    'static'] and not request.endpoint.startswith('static'):
                return redirect(url_for('main.login'))

    # ========================================================================
    # Global Error Handlers
    # ========================================================================

    from app.core.exceptions import (
        PersonalGuruException,
        ValidationError,
        AuthenticationError,
        ResourceNotFoundError,
        DatabaseError,
        LLMError
    )

    logger = logging.getLogger(__name__)

    def is_json_request():
        """Check if the request expects a JSON response."""
        return request.is_json or request.path.startswith(
            '/api/') or 'application/json' in request.headers.get('Accept', '')

    @app.errorhandler(PersonalGuruException)
    def handle_app_exception(error):
        """Handle all custom application exceptions."""
        # Log the exception
        error.log(logger, endpoint=request.endpoint or request.path)

        if is_json_request():
            return jsonify({
                'error': error.user_message,
                'error_code': error.error_code,
                'status': 'error'
            }), error.http_status
        else:
            # Render error template with user-friendly message
            return render_template(
                'error.html',
                error_code=error.error_code,
                error_message=error.user_message,
                http_status=error.http_status
            ), error.http_status

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        """Handle validation errors (400)."""
        error.log(logger, endpoint=request.endpoint or request.path)

        if is_json_request():
            return jsonify({
                'error': error.user_message,
                'error_code': error.error_code,
                'field': error.debug_info.get('field'),
                'status': 'validation_error'
            }), 400
        else:
            return render_template(
                'error.html',
                error_code=error.error_code,
                error_message=error.user_message,
                http_status=400
            ), 400

    @app.errorhandler(AuthenticationError)
    def handle_auth_error(error):
        """Handle authentication errors (401)."""
        error.log(logger, endpoint=request.endpoint or request.path)

        if is_json_request():
            return jsonify({
                'error': error.user_message,
                'error_code': error.error_code,
                'status': 'unauthorized'
            }), 401
        else:
            # Redirect to login page
            return redirect(url_for('main.login'))

    @app.errorhandler(ResourceNotFoundError)
    def handle_not_found(error):
        """Handle resource not found errors (404)."""
        error.log(logger, endpoint=request.endpoint or request.path)

        if is_json_request():
            return jsonify({
                'error': error.user_message,
                'error_code': error.error_code,
                'status': 'not_found'
            }), 404
        else:
            return render_template(
                'error.html',
                error_code=error.error_code,
                error_message=error.user_message,
                http_status=404
            ), 404

    @app.errorhandler(DatabaseError)
    def handle_database_error(error):
        """Handle database errors (500)."""
        error.log(logger, endpoint=request.endpoint or request.path)

        if is_json_request():
            return jsonify({
                'error': error.user_message,
                'error_code': error.error_code,
                'status': 'database_error',
                'retry': error.should_retry
            }), 500
        else:
            return render_template(
                'error.html',
                error_code=error.error_code,
                error_message=error.user_message,
                can_retry=error.should_retry,
                http_status=500
            ), 500

    @app.errorhandler(LLMError)
    def handle_llm_error(error):
        """Handle LLM/AI service errors (503)."""
        error.log(logger, endpoint=request.endpoint or request.path)

        if is_json_request():
            return jsonify({
                'error': error.user_message,
                'error_code': error.error_code,
                'status': 'service_unavailable',
                'retry': error.should_retry
            }), 503
        else:
            return render_template(
                'error.html',
                error_code=error.error_code,
                error_message=error.user_message,
                can_retry=error.should_retry,
                http_status=503
            ), 503

    @app.errorhandler(404)
    def handle_404(error):
        """Handle standard 404 errors."""
        logger.warning(f"404 Not Found: {request.path}")

        if is_json_request():
            return jsonify({
                'error': 'The requested resource was not found.',
                'status': 'not_found'
            }), 404
        else:
            return render_template(
                'error.html',
                error_code='404',
                error_message='The page you are looking for does not exist.',
                http_status=404
            ), 404

    @app.errorhandler(500)
    def handle_500(error):
        """Handle standard 500 errors."""
        logger.error(f"500 Internal Server Error: {str(error)}", exc_info=True)

        if is_json_request():
            return jsonify({
                'error': 'An internal server error occurred. Please try again later.',
                'status': 'error'
            }), 500
        else:
            return render_template(
                'error.html',
                error_code='500',
                error_message='We encountered a technical problem. Please try again later.',
                http_status=500
            ), 500

    # Initialize Background Sync
    # In debug mode with reloader, the parent process spawns a child.
    # WERKZEUG_RUN_MAIN is 'true' ONLY in the child process.
    # We skip starting in the parent (where WERKZEUG_RUN_MAIN is not set but reloader is active)
    # to avoid double initialization and incorrect config.
    # In production (without reloader), WERKZEUG_RUN_MAIN won't be set, so we also start.
    run_main_env = os.environ.get('WERKZEUG_RUN_MAIN')
    is_frozen = getattr(sys, 'frozen', False)  # PyInstaller sets this

    # Start sync if:
    # 1. We're in the reloader child process (WERKZEUG_RUN_MAIN='true')
    # 2. We're in production/frozen mode (no reloader, WERKZEUG_RUN_MAIN not set)
    # 3. We're in a standard run (no debug, no reloader) - e.g. Docker default

    if is_frozen:
        should_start_sync = True
    elif app.debug:
        should_start_sync = (run_main_env == 'true')
    else:
        # Not frozen, not debug. Likely Docker or production run.
        should_start_sync = True

    # Do not start sync in TESTING mode
    if app.config.get('TESTING'):
        should_start_sync = False

    if os.environ.get('SKIP_BACKGROUND_TASKS') == 'True':
        should_start_sync = False

    if not app.config.get('ENABLE_TELEMETRY', True):
        should_start_sync = False

    # DEBUG: Trace startup logic
    print("=== STARTUP DEBUG ===")
    print(f"is_frozen: {is_frozen}")
    print(f"app.debug: {app.debug}")
    print(f"WERKZEUG_RUN_MAIN: {run_main_env}")
    print(f"should_start_sync: {should_start_sync} (Background Manager)")
    print(f"OFFLINE_MODE: {os.getenv('OFFLINE_MODE', 'False')}")
    print(f"ENABLE_TELEMETRY: {app.config.get('ENABLE_TELEMETRY', True)}")
    print("=====================")

    if should_start_sync:
        # Main server process - start background services
        try:
            from app.common.dcs import SyncManager
            sync_manager = SyncManager(app)
            sync_manager.start()
        except Exception as e:
            logger.error(f"Failed to start SyncManager: {e}")

        # Initialize Shared Sandbox for code execution
        try:
            from app.common.sandbox import ensure_shared_sandbox
            ensure_shared_sandbox()
        except Exception as e:
            logger.error(f"Failed to initialize shared sandbox: {e}")

        # Initialize Audio Services (TTS/STT)
        try:
            from app.common.audio_service import init_audio_services
            init_audio_services()
        except Exception as e:
            logger.warning(f"Audio services initialization failed: {e}")

    return app
