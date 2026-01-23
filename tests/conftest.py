import pytest
import sys
from unittest.mock import MagicMock

# Mock weasyprint to avoid GTK dependency issues during tests
sys.modules['weasyprint'] = MagicMock()
sys.modules['weasyprint.HTML'] = MagicMock()

from app import create_app  # noqa: E402
from app.core.models import db  # noqa: E402

def pytest_addoption(parser):
    parser.addoption(
        "--show-llm-responses", action="store_true", default=False, help="Show LLM responses in output"
    )

@pytest.fixture
def show_llm_responses(request):
    return request.config.getoption("--show-llm-responses")

class TestLogger:
    def __init__(self, enabled):
        self.enabled = enabled

    def section(self, title):
        if self.enabled:
            print(f"\n\n{'='*80}\n🚀 TEST: {title}\n{'='*80}")

    def step(self, message):
        if self.enabled:
            print(f"\n👉 {message}")

    def response(self, label, content):
        if self.enabled:
            print(f"\n📝 {label}:\n{'-'*40}\n{content}\n{'-'*40}")

    def info(self, message):
        if self.enabled:
            print(f"   ℹ️  {message}")

@pytest.fixture
def logger(show_llm_responses):
    return TestLogger(show_llm_responses)

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })

    with app.app_context():
        # Import models to register them with SQLAlchemy before create_all
        from app.core.models import User, Login, Topic, Installation
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def auth_client(client, app):
    """A logged-in test client."""
    from app.core.models import User

    with app.app_context():

        from app.core.models import Login
        if not Login.query.filter_by(username='testuser').first():
            import uuid
            uid = str(uuid.uuid4())
            login = Login(userid=uid, username='testuser', name='Test User')
            login.set_password('password')
            db.session.add(login)

            user = User(login_id=uid)
            db.session.add(user)
            db.session.commit()

    # Login
    client.post('/login', data={'username': 'testuser', 'password': 'password'}, follow_redirects=True)
    return client
