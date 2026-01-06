from flask import Flask, request, redirect, url_for, jsonify, render_template
from config import Config
from .core.extensions import db, migrate
from flask_wtf.csrf import CSRFProtect
from flask_session import Session  # Server-side sessions for large chat histories
from flask_login import LoginManager
import logging

csrf = CSRFProtect()
sess = Session()

login_manager = LoginManager()
login_manager.login_view = 'main.login'


def create_app(config_class=Config):
    app = Flask(__name__, template_folder='core/templates')
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    sess.init_app(app)  # Initialize server-side sessions
    login_manager.init_app(app)

    from app.core.models import User

    @login_manager.user_loader
    def load_user(username):
        return User.query.get(username)

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
                    'static'] and not request.endpoint.startswith('static'):
                return redirect(url_for('main.login'))

    # ========================================================================
    # Global Error Handlers
    # ========================================================================

    from app.core.exceptions import (
        PersonalGuruException,
        ClientError,
        ValidationError,
        AuthenticationError,
        AuthorizationError,
        ResourceNotFoundError,
        ServerError,
        DatabaseError,
        ExternalServiceError,
        LLMError,
        ConfigurationError
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

    return app
