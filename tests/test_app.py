import pytest
from unittest.mock import patch, MagicMock
from app.common.utils import summarize_text
from app.core.models import TelemetryLog
from app.core.exceptions import TopicNotFoundError, ValidationError
from app.common.config_validator import validate_config

from app.setup_app import create_setup_app
from app.common.log_capture import LogCapture
import time

# Mark all tests in this file as 'unit'
pytestmark = pytest.mark.unit

def test_home_page(auth_client, mocker, logger):
    """Test that the home page loads correctly."""
    logger.section("test_home_page")
    mocker.patch('app.core.routes.get_all_topics', return_value=[])
    response = auth_client.get('/')
    logger.step("GET /")
    assert response.status_code == 200
    assert b"What would you like to learn today?" in response.data

def test_full_learning_flow(auth_client, mocker, logger):
    """Test the full user flow from topic submission to finishing the course."""
    logger.section("test_full_learning_flow")
    topic_name = "testing"

    # Mock PlannerAgent
    mocker.patch('app.common.agents.PlannerAgent.generate_study_plan', return_value=['Step 1', 'Step 2'])

    # Mock TopicTeachingAgent (ChapterTeachingAgent)
    mocker.patch('app.modes.chapter.routes.ChapterTeachingAgent.generate_teaching_material', return_value="## Step Content")

    # Mock AssessorAgent
    mocker.patch('app.modes.chapter.routes.AssessorAgent.generate_question', return_value={
        "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": "A"}]
    })

    # Mock storage functions
    mocker.patch('app.core.routes.load_topic', return_value=None)
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=None)
    mocker.patch('app.modes.chapter.routes.save_topic', return_value=None)
    mocker.patch('app.core.routes.get_all_topics', return_value=[])

    # 1. User submits a new topic
    logger.step("1. User submits a new topic")
    response = auth_client.post('/', data={'topic': topic_name})
    assert response.status_code == 302
    # Redirects to /chapter/testing -> then /chapter/learn/testing/0
    # But wait, initially load_topic returns None.
    # chapter.mode:
    #   planner.generate_study_plan -> saves topic -> redirect(url_for('chapter.learn_topic', ...))
    # So location should be /chapter/learn/testing/0
    assert response.headers['Location'] == f'/chapter/{topic_name}'

    # Follow the redirect to /chapter/testing
    logger.step("Following redirect to /chapter/testing")
    mocker.patch('app.modes.chapter.routes.load_topic', return_value={"name": topic_name, "plan": ["Step 1", "Step 2"], "chapter_mode": [{}, {}]})
    response = auth_client.get(f'/chapter/{topic_name}')
    assert response.status_code == 302
    assert response.headers['Location'] == f'/chapter/learn/{topic_name}/0'

    # Mock storage.load_topic to return the created topic data
    topic_data = {
        "name": topic_name,
        "plan": ["Step 1", "Step 2"],
        "chapter_mode": [
            {},
            {}
        ]
    }
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=topic_data)

    # 2. User follows the redirect to the first learning step
    logger.step("2. User follows the redirect to the first learning step")
    response = auth_client.get(f'/chapter/learn/{topic_name}/0')
    assert response.status_code == 200
    assert b"Step 1" in response.data
    assert b'<div id="step-content-markdown" style="display: none;">## Step Content</div>' in response.data

    # 3. User submits an answer
    logger.step("3. User submits an answer")
    topic_data['chapter_mode'][0] = {"teaching_material": "## Step Content", "questions": {"questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": "A"}]}}
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=topic_data)
    response = auth_client.post(f'/chapter/assess/{topic_name}/0', data={'option_0': 'A'})
    assert response.status_code == 200
    assert b"Your Score: 100.0%" in response.data

    # 4. User continues to the next step
    logger.step("4. User continues to the next step")
    topic_data['chapter_mode'][0]['user_answers'] = ['A']
    topic_data['chapter_mode'][0]['completed'] = True
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=topic_data)
    response = auth_client.get(f'/chapter/learn/{topic_name}/1')
    assert response.status_code == 200
    assert b"Check Your Understanding" in response.data # Check that assessment is shown

    # 5. User goes back to the previous step
    logger.step("5. User goes back to the previous step")
    response = auth_client.get(f'/chapter/learn/{topic_name}/0')
    assert response.status_code == 200
    assert b"Check Your Understanding" in response.data
    # Check that assessment form is not shown (action URL absent implies form absent or different)
    assert b'action="/chapter/assess/testing/0"' not in response.data

    # 6. User finishes the course
    logger.step("6. User finishes the course")
    topic_data['chapter_mode'][1] = {"teaching_material": "## Step 2 Content", "questions": {"questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": "C"}]}}
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=topic_data)
    response = auth_client.post(f'/chapter/assess/{topic_name}/1', data={'option_0': 'C'})
    assert response.status_code == 302
    assert response.headers['Location'] == f'/chapter/complete/{topic_name}'

    # 7. User sees the completion page
    logger.step("7. User sees the completion page")
    response = auth_client.get(f'/chapter/complete/{topic_name}')
    assert response.status_code == 200
    assert b"Congratulations!" in response.data

def test_export_topic(auth_client, mocker, logger):
    """Test the export functionality."""
    logger.section("test_export_topic")
    topic_name = "export_test"
    topic_data = {
        "name": topic_name,
        "plan": ["Step 1"],
        "chapter_mode": [{"teaching_material": "## Test Content"}]
    }
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=topic_data)

    response = auth_client.get(f'/chapter/export/{topic_name}')
    logger.step(f"Exporting topic: {topic_name}")
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == f'attachment; filename={topic_name}.md'
    assert response.data == b'# export_test\n\n## Step 1\n\n## Test Content\n\n'

def test_delete_topic(auth_client, mocker, logger):
    """Test deleting a topic."""
    logger.section("test_delete_topic")
    topic_name = "delete_test"
    mocker.patch('app.core.routes.get_all_topics', return_value=[topic_name])

    # Check that the topic is listed
    response = auth_client.get('/')
    assert bytes(topic_name, 'utf-8') in response.data

    # Delete the topic
    logger.step(f"Deleting topic: {topic_name}")
    mocker.patch('app.common.storage.delete_topic', return_value=None)
    response = auth_client.get(f'/delete/{topic_name}')
    assert response.status_code == 302
    assert response.headers['Location'] == '/'

    # Check that the topic is no longer listed
    mocker.patch('app.core.routes.get_all_topics', return_value=[])
    response = auth_client.get('/')
    assert bytes(topic_name, 'utf-8') not in response.data

def test_chat_route(auth_client, mocker, logger):
    """Test the chat functionality."""
    logger.section("test_chat_route")
    topic_name = "chat_test"
    topic_data = {
        "name": topic_name,
        "description": "A topic for testing chat.",
        "chat_history": [],
        "plan": ["Introduction"]
    }
    mocker.patch('app.modes.chat.routes.load_topic', return_value=topic_data)
    mocker.patch('app.modes.chat.agent.ChatModeMainChatAgent.get_welcome_message', return_value="Welcome to the chat!")
    mocker.patch('app.common.agents.ChatAgent.get_answer', return_value="This is the answer.")
    mocker.patch('app.modes.chat.routes.save_chat_history')

    # Test initial GET request to establish the session and get welcome message
    logger.step("Initial GET request")
    response = auth_client.get(f'/chat/{topic_name}')
    assert response.status_code == 200
    assert b"Welcome to the chat!" in response.data

    # Test POST request to send a message
    logger.step("POST request to send a message")
    response = auth_client.post(f'/chat/{topic_name}/send', data={'message': 'hello world'}, follow_redirects=True)
    if b"This is the answer." not in response.data:
        print("\nDEBUG RESPONSE DATA:\n", response.data, "\n")
    assert response.status_code == 200
    assert b"hello world" in response.data
    assert b"This is the answer." in response.data

def test_suggestions_unauthorized(client):
    """Test that the suggestions endpoint requires login."""
    response = client.get('/api/suggest-topics')
    assert response.status_code == 302 # Redirect to login
    assert '/login' in response.headers['Location']

def test_suggestions_success(auth_client, mocker, logger):
    """Test successful generation of topic suggestions."""
    logger.section("test_suggestions_success")

    # Mock data
    past_topics = ['Python', 'History']
    suggested_topics = ['Math', 'Science', 'Art']

    # Mock storage
    mocker.patch('app.common.storage.get_all_topics', return_value=past_topics)

    # Mock Agent
    mocker.patch('app.common.agents.SuggestionAgent.generate_suggestions', return_value=(suggested_topics, None))

    logger.step("Calling suggestions API")
    response = auth_client.get('/api/suggest-topics')

    assert response.status_code == 200
    data = response.get_json()

    logger.step(f"Received suggestions: {data}")
    assert 'suggestions' in data
    assert data['suggestions'] == suggested_topics
    assert len(data['suggestions']) == 3

def test_suggestions_agent_error(auth_client, mocker, logger):
    """Test error handling when the agent fails."""
    logger.section("test_suggestions_agent_error")

    # Mock storage
    mocker.patch('app.common.storage.get_all_topics', return_value=[])

    # Mock Agent failure
    error_message = "LLM failure"
    mocker.patch('app.common.agents.SuggestionAgent.generate_suggestions', return_value=([], error_message))

    logger.step("Calling suggestions API (expecting error)")
    response = auth_client.get('/api/suggest-topics')

    assert response.status_code == 500
    data = response.get_json()

    logger.step(f"Received error: {data}")
    logger.step(f"Received error: {data}")
    assert 'error' in data
    assert data['error'] == error_message


# --- New Tests for Config & Setup ---

def test_validate_config_all_present(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/db")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("LLM_MODEL_NAME", "llama3")

    missing = validate_config()
    assert len(missing) == 0

def test_validate_config_missing_vars(monkeypatch):
    # Ensure they are unset
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)

    missing = validate_config()
    assert "LLM_BASE_URL" in missing
    assert "LLM_MODEL_NAME" in missing

def test_validate_config_partial_missing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/db") # Set but not checked
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_MODEL_NAME", "llama3")

    missing = validate_config()
    assert "LLM_BASE_URL" in missing

@pytest.fixture
def setup_client():
    app = create_setup_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    with app.test_client() as client:
        yield client

def test_setup_page_loads(setup_client):
    rv = setup_client.get('/')
    assert rv.status_code == 200
    assert b"Configure Personal Guru" in rv.data

def test_setup_submission(setup_client):
    rv = setup_client.post('/', data={
        'database_url': '',
        'LLM_BASE_URL': ''
    })
    assert rv.status_code == 400
    assert b"Missing required fields" in rv.data

def test_setup_success_mock_fs(setup_client, mocker):
    m = mocker.mock_open()
    mocker.patch('builtins.open', m)

    rv = setup_client.post('/', data={
        'database_url': 'postgresql://test',
        'port': '5011',
        'LLM_BASE_URL': 'http://test',
        'llm_model': 'gpt-4',
        'llm_key': 'secret',
        'llm_ctx': '20000',
        'tts_url': 'http://kokoro',
        'openai_key': 'tts-secret',
        'youtube_key': 'yt123'
    })

    assert rv.status_code == 200
    assert b"Configuration Saved!" in rv.data

    # Verify file write
    # Verify file write
    # m.assert_called_with('.env', 'w') -> Relaxed check for absolute paths
    args, kwargs = m.call_args
    assert args[0].endswith('.env')
    assert args[1] == 'w'
    handle = m()

    # Collect all content written
    written_content = ""
    for call in handle.write.call_args_list:
        written_content += call[0][0]

    assert "DATABASE_URL=postgresql://test" in written_content
    assert "LLM_NUM_CTX=20000" in written_content
    assert "TTS_BASE_URL=http://kokoro" in written_content
    assert "OPENAI_API_KEY=tts-secret" in written_content
    assert "OPENAI_API_KEY=tts-secret" in written_content
    assert "YOUTUBE_API_KEY=yt123" in written_content


def test_transcribe_api(auth_client, mocker, logger):
    """Test the /api/transcribe endpoint."""
    logger.section("test_transcribe_api")

    # Mock transcribe_audio utility
    mocker.patch('app.common.utils.transcribe_audio', return_value="Hello world")

    # Create a dummy audio file
    from io import BytesIO
    data = {
        'audio': (BytesIO(b"fake audio data"), 'test.wav')
    }

    response = auth_client.post('/api/transcribe', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    json_data = response.get_json()
    assert 'transcript' in json_data
    assert json_data['transcript'] == "Hello world"

    # Test error case
    mocker.patch('app.common.utils.transcribe_audio', side_effect=Exception("Transcribe failed"))
    data_err = {
        'audio': (BytesIO(b"fake audio data"), 'test.wav')
    }
    response = auth_client.post('/api/transcribe', data=data_err, content_type='multipart/form-data')

    assert response.status_code == 500
    json_data = response.get_json()
    assert 'error' in json_data
    assert json_data['error'] == "Transcribe failed"


# --- Consolidated Tests from test_summarization.py ---

def test_summarize_text_function():
    with patch('app.common.utils.call_llm') as mock_llm:
        mock_llm.return_value = "Summary: Short text."

        text = "This is a very long text that needs summarization. " * 10
        summary = summarize_text(text)

        assert summary == "Summary: Short text."
        mock_llm.assert_called_once()
        args, _ = mock_llm.call_args
        assert "Requirements:" in args[0]


# --- Consolidated Tests from test_exception_handling.py ---

def test_404_not_found(client):
    """Test that non-existent routes return 404 with correct error format."""
    response = client.get('/non-existent-route')
    assert response.status_code == 404
    assert b"The page you are looking for does not exist" in response.data

def test_api_404_not_found(client):
    """Test that API 404 returns JSON."""
    response = client.get('/api/non-existent', headers={"Content-Type": "application/json"})
    assert response.status_code == 404
    assert response.is_json
    data = response.get_json()
    assert data['status'] == 'not_found'

@pytest.fixture
def client_no_auth(app):
    app.config['LOGIN_DISABLED'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app.test_client()

def test_storage_not_found_handling(client_no_auth):
    """Test handling of TopicNotFoundError."""
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.username = 'testuser'

    with patch('flask_login.utils._get_user', return_value=mock_user), \
         patch('app.common.storage.current_user', mock_user):

        with patch('app.modes.chapter.routes.load_topic') as mock_load:
            mock_load.side_effect = TopicNotFoundError("MissingTopic")

            response = client_no_auth.get('/chapter/learn/MissingTopic/0')

            assert response.status_code == 404
            # Check for partial match to avoid quote escaping issues
            assert b"MissingTopic" in response.data

def test_validation_error_handling(client_no_auth):
    """Test handling of ValidationError."""
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.username = 'testuser'

    with patch('flask_login.utils._get_user', return_value=mock_user), \
         patch('app.common.storage.current_user', mock_user):

        with patch('app.modes.quiz.routes.load_topic') as mock_load:
            mock_load.side_effect = ValidationError("Invalid input data", error_code="VAL001")

            response = client_no_auth.get('/quiz/InvalidTopic')

            assert response.status_code == 400
            assert b"Please check your input and try again" in response.data

def test_get_system_info(mocker):
    """Test get_system_info utility across different scenarios."""
    from app.common.utils import get_system_info

    # Mock basic system deps
    mocker.patch('app.common.utils.os.cpu_count', return_value=8)
    mock_psutil = mocker.patch('app.common.utils.psutil')
    mock_psutil.virtual_memory.return_value.total = 16 * 1024**3 # 16GB
    mocker.patch('app.common.utils.platform.platform', return_value="Linux-Test")
    mocker.patch('app.common.utils.os.path.exists', side_effect=lambda x: x == '/.dockerenv') # Simulate Docker

    # 1. Test NVIDIA GPU path
    mock_run = mocker.patch('app.common.utils.subprocess.run')
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "GPU 0: NVIDIA Test (UUID: 123)"

    info = get_system_info()
    assert info['cpu_cores'] == 8
    assert info['ram_gb'] == 16
    assert info['install_method'] == 'docker'
    assert info['gpu_model'] == "GPU 0: NVIDIA Test (UUID: 123)"
    assert info['os_version'] == "Linux-Test"

    # 2. Test AMD GPU path (NVIDIA fails, AMD succeeds)
    def side_effect_amd(cmd, **kwargs):
        res = MagicMock()
        if 'nvidia-smi' in cmd:
            res.returncode = 1
        elif 'rocm-smi' in cmd:
            res.returncode = 0
            res.stdout = "AMD Radeon Test"
        return res

    mock_run.side_effect = side_effect_amd
    info = get_system_info()
    assert info['gpu_model'] == "AMD AMD Radeon Test"

    # 3. Test No GPU
    mock_run.side_effect = FileNotFoundError
    info = get_system_info()
    assert info['gpu_model'] == "Unknown"


def test_log_telemetry(mocker):
    """Test the log_telemetry utility function."""
    from app.common.utils import log_telemetry
    from app.core.models import TelemetryLog

    # Mock current_user
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.userid = 'test_user_123'
    mock_user.installation_id = 'inst_123'

    # Mock db and session where they are defined/imported
    # log_telemetry imports them inside the function, so we patch the source
    mock_db = mocker.patch('app.core.extensions.db')

    # Mock flask session
    # We need to mock the dict behavior of session
    mock_session = {}
    mocker.patch('flask.session', mock_session)

    # Mock flask_login.current_user
    mocker.patch('flask_login.current_user', mock_user)

    # Mock Installation model for fallback
    mock_installation_cls = mocker.patch('app.core.models.Installation')

    # 1. Test successful logging (User has installation_id)
    log_telemetry(
        event_type='unit_test_event',
        triggers={'source': 'test'},
        payload={'data': 'value'}
    )

    # Verify db.session.add was called with a TelemetryLog object
    assert mock_db.session.add.called
    args, _ = mock_db.session.add.call_args
    log_entry = args[0]

    assert isinstance(log_entry, TelemetryLog)
    assert log_entry.user_id == 'test_user_123'
    assert log_entry.installation_id == 'inst_123'
    assert log_entry.event_type == 'unit_test_event'
    assert log_entry.triggers == {'source': 'test'}
    assert log_entry.payload == {'data': 'value'}
    assert 'telemetry_session_id' in mock_session
    assert log_entry.session_id == mock_session['telemetry_session_id']

    assert mock_db.session.commit.called

    # 2. Test explicit installation_id (overrides user)
    mock_db.session.add.reset_mock()
    log_telemetry('explicit_event', {}, {}, installation_id='explicit_inst_999')
    args, _ = mock_db.session.add.call_args
    log_entry = args[0]
    assert log_entry.installation_id == 'explicit_inst_999'

    # 3. Test unauthenticated user BUT with installation lookup
    mock_user.is_authenticated = False
    mock_db.session.add.reset_mock()

    # Mock Installation.query.first()
    mock_inst_record = MagicMock()
    mock_inst_record.installation_id = 'fallback_inst_456'
    mock_installation_cls.query.first.return_value = mock_inst_record

    log_telemetry('anon_event', {}, {})
    assert mock_db.session.add.called
    args, _ = mock_db.session.add.call_args
    log_entry = args[0]
    assert log_entry.user_id is None
    assert log_entry.installation_id == 'fallback_inst_456'

    # 4. Test missing installation_id (should skip)
    mock_installation_cls.query.first.return_value = None
    mock_db.session.add.reset_mock()
    log_telemetry('skip_event', {}, {})
    assert not mock_db.session.add.called

    # 5. Test exception handling (should fail silently)
    # Restore auth user for easy path
    mock_user.is_authenticated = True
    mock_db.session.add.side_effect = Exception("DB Error")

    try:
         log_telemetry('fail_event', {}, {})
    except Exception:
         pytest.fail("log_telemetry raised exception instead of failing silently")

def test_log_capture_threading():
    """Test that log capture correctly buffers and flushes logs using background thread."""
    import uuid

    # Generate unique log messages to avoid collision with other logs
    unique_id = str(uuid.uuid4())[:8]
    test_log_1 = f"TestLogCapture_{unique_id}_Log1"
    test_log_2 = f"TestLogCapture_{unique_id}_Log2"

    # Mock app and database session
    mock_app = MagicMock()
    mock_app.app_context.return_value.__enter__.return_value = None

    # Mock Installation query
    mock_installation = MagicMock()
    mock_installation.installation_id = "test_install_id"

    with patch('app.core.models.Installation') as mock_inst_cls, \
         patch('app.core.extensions.db.session') as mock_session:

        mock_inst_cls.query.first.return_value = mock_installation

        # Reset singleton for test
        with LogCapture._lock:
            LogCapture._instance = None

        capture = LogCapture(None)
        capture.app = mock_app

        # Configure short flush interval
        capture.flush_interval = 0.5
        capture.batch_size = 10

        # Verify worker thread started
        assert capture.worker_thread.is_alive()

        # 1. Test Buffering - use unique log messages
        print(test_log_1)
        print(test_log_2)

        # Wait for flush
        time.sleep(1.5)

        # Verify database interaction
        assert mock_session.add.called

        # Collect all log messages from all add calls
        all_logged_messages = []
        for call in mock_session.add.call_args_list:
            log_entry = call[0][0]
            if isinstance(log_entry, TelemetryLog) and log_entry.event_type == 'terminal_log':
                for log_item in log_entry.payload.get('logs', []):
                    all_logged_messages.append(log_item['message'].strip())

        # Verify our specific log messages were captured
        assert any(test_log_1 in msg for msg in all_logged_messages), \
            f"Expected '{test_log_1}' not found in captured logs: {all_logged_messages}"
        assert any(test_log_2 in msg for msg in all_logged_messages), \
            f"Expected '{test_log_2}' not found in captured logs: {all_logged_messages}"

        # Cleanup
        capture.stop()
        with LogCapture._lock:
            LogCapture._instance = None


# --- Consolidated Tests from test_dcs_manual.py ---

@pytest.fixture
def dcs_app():
    """Create a fresh app and database for DCS tests."""
    from app import create_app
    from app.core.extensions import db
    from config import TestConfig

    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_dcs_registration(dcs_app, mocker):
    """Test DCS device registration flow."""
    from app.core.extensions import db
    from app.core.models import Installation
    from app.common.dcs import DCSClient

    with dcs_app.app_context():
        # Setup mocks
        mocker.patch('app.common.utils.get_system_info', return_value={
            'cpu_cores': 4, 'ram_gb': 16, 'gpu_model': 'TestGPU',
            'os_version': 'TestOS', 'install_method': 'test'
        })

        # Mock Register Response
        mock_reg_resp = MagicMock()
        mock_reg_resp.status_code = 201
        mock_reg_resp.json.return_value = {"installation_id": "test-uuid-1234"}

        # Mock Update Response
        mock_update_resp = MagicMock()
        mock_update_resp.status_code = 200
        mock_update_resp.json.return_value = {"status": "updated"}

        mocker.patch('app.common.dcs.requests.post',
                     side_effect=[mock_reg_resp, mock_update_resp])

        client = DCSClient()
        success = client.register_device()

        assert success is True
        assert client.installation_id == "test-uuid-1234"

        # Verify DB
        inst = Installation.query.first()
        assert inst is not None
        assert inst.installation_id == "test-uuid-1234"


def test_dcs_sync(dcs_app, mocker):
    """Test DCS data synchronization flow."""
    from app.core.extensions import db
    from app.core.models import Installation, Topic, SyncLog, Feedback, AIModelPerformance
    from app.common.dcs import DCSClient

    with dcs_app.app_context():
        # Pre-seed installation
        inst = Installation(installation_id="test-uuid-sync", install_method="test")
        db.session.add(inst)

        # Add some data
        topic = Topic(name="Test Topic", user_id="test_user", sync_status="pending")
        db.session.add(topic)

        # Add feedback and performance data
        fb = Feedback(user_id="test_user", feedback_type="in_place",
                      comment="Great!", sync_status="pending")
        db.session.add(fb)

        perf = AIModelPerformance(user_id="test_user", model_type="LLM",
                                   latency_ms=100, sync_status="pending")
        db.session.add(perf)

        db.session.commit()

        # Mock Sync Response
        mock_sync_resp = MagicMock()
        mock_sync_resp.status_code = 200
        mocker.patch('app.common.dcs.requests.post', return_value=mock_sync_resp)

        client = DCSClient()
        client.sync_data()

        # Verify Sync Status
        t = Topic.query.first()
        assert t.sync_status == 'synced'

        fb_query = Feedback.query.first()
        assert fb_query.sync_status == 'synced'

        perf_query = AIModelPerformance.query.first()
        assert perf_query.sync_status == 'synced'

        # Verify SyncLog
        log = SyncLog.query.first()
        assert log is not None
        assert log.status == 'success'
