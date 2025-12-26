import pytest
from app import create_app
from app.common.models import db

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
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()
