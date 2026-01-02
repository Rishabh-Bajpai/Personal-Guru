import pytest
from app.core.config_validator import validate_config
from app.setup_app import create_setup_app

# Mark all tests in this file as 'unit'
pytestmark = pytest.mark.unit

def test_home_page(auth_client, mocker, logger):
    """Test that the home page loads correctly."""
    logger.section("test_home_page")
    mocker.patch('app.common.routes.get_all_topics', return_value=[])
    response = auth_client.get('/')
    logger.step("GET /")
    assert response.status_code == 200
    assert b"What would you like to learn today?" in response.data

def test_full_learning_flow(auth_client, mocker, logger):
    """Test the full user flow from topic submission to finishing the course."""
    logger.section("test_full_learning_flow")
    topic_name = "testing"

    # Mock PlannerAgent
    mocker.patch('app.core.agents.PlannerAgent.generate_study_plan', return_value=(['Step 1', 'Step 2'], None))

    # Mock TopicTeachingAgent (ChapterTeachingAgent)
    mocker.patch('app.modes.chapter.routes.ChapterTeachingAgent.generate_teaching_material', return_value=("## Step Content", None))

    # Mock AssessorAgent
    mocker.patch('app.modes.chapter.routes.AssessorAgent.generate_question', return_value=({
        "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": "A"}]
    }, None))

    # Mock storage functions
    mocker.patch('app.common.routes.load_topic', return_value=None)
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=None)
    mocker.patch('app.modes.chapter.routes.save_topic', return_value=None)
    mocker.patch('app.common.routes.get_all_topics', return_value=[])

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
    mocker.patch('app.modes.chapter.routes.load_topic', return_value={"name": topic_name, "plan": ["Step 1", "Step 2"], "steps": [{}, {}]})
    response = auth_client.get(f'/chapter/{topic_name}')
    assert response.status_code == 302
    assert response.headers['Location'] == f'/chapter/learn/{topic_name}/0'

    # Mock storage.load_topic to return the created topic data
    topic_data = {
        "name": topic_name,
        "plan": ["Step 1", "Step 2"],
        "steps": [
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
    topic_data['steps'][0] = {"teaching_material": "## Step Content", "questions": {"questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": "A"}]}}
    mocker.patch('app.modes.chapter.routes.load_topic', return_value=topic_data)
    response = auth_client.post(f'/chapter/assess/{topic_name}/0', data={'option_0': 'A'})
    assert response.status_code == 200
    assert b"Your Score: 100.0%" in response.data

    # 4. User continues to the next step
    logger.step("4. User continues to the next step")
    topic_data['steps'][0]['user_answers'] = ['A']
    topic_data['steps'][0]['completed'] = True
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
    topic_data['steps'][1] = {"teaching_material": "## Step 2 Content", "questions": {"questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": "C"}]}}
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
        "steps": [{"teaching_material": "## Test Content"}]
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
    mocker.patch('app.common.routes.get_all_topics', return_value=[topic_name])

    # Check that the topic is listed
    response = auth_client.get('/')
    assert bytes(topic_name, 'utf-8') in response.data

    # Delete the topic
    logger.step(f"Deleting topic: {topic_name}")
    mocker.patch('app.core.storage.delete_topic', return_value=None)
    response = auth_client.get(f'/delete/{topic_name}')
    assert response.status_code == 302
    assert response.headers['Location'] == '/'

    # Check that the topic is no longer listed
    mocker.patch('app.common.routes.get_all_topics', return_value=[])
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
    mocker.patch('app.modes.chat.agent.ChatModeMainChatAgent.get_welcome_message', return_value=("Welcome to the chat!", None))
    mocker.patch('app.core.agents.ChatAgent.get_answer', return_value=("This is the answer.", None))
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
    mocker.patch('app.core.storage.get_all_topics', return_value=past_topics)
    
    # Mock Agent
    mocker.patch('app.core.agents.SuggestionAgent.generate_suggestions', return_value=(suggested_topics, None))
    
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
    mocker.patch('app.core.storage.get_all_topics', return_value=[])
    
    # Mock Agent failure
    error_message = "LLM failure"
    mocker.patch('app.core.agents.SuggestionAgent.generate_suggestions', return_value=([], error_message))
    
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
    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("LLM_MODEL_NAME", "llama3")
    
    missing = validate_config()
    assert len(missing) == 0

def test_validate_config_missing_vars(monkeypatch):
    # Ensure they are unset
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    
    missing = validate_config()
    assert "DATABASE_URL" in missing
    assert "LLM_ENDPOINT" in missing
    assert "LLM_MODEL_NAME" in missing

def test_validate_config_partial_missing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/db")
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    monkeypatch.setenv("LLM_MODEL_NAME", "llama3")
    
    missing = validate_config()
    assert "LLM_ENDPOINT" in missing
    assert "DATABASE_URL" not in missing

@pytest.fixture
def setup_client():
    app = create_setup_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_setup_page_loads(setup_client):
    rv = setup_client.get('/')
    assert rv.status_code == 200
    assert b"Welcome to Personal Guru" in rv.data

def test_setup_submission(setup_client):
    rv = setup_client.post('/', data={
        'database_url': '',
        'llm_endpoint': ''
    })
    assert rv.status_code == 400
    assert b"Missing required fields" in rv.data

def test_setup_success_mock_fs(setup_client, mocker):
    m = mocker.mock_open()
    mocker.patch('builtins.open', m)
    
    rv = setup_client.post('/', data={
        'database_url': 'postgresql://test',
        'llm_endpoint': 'http://test',
        'llm_model': 'gpt-4',
        'llm_key': 'secret'
    })
    
    assert rv.status_code == 200
    assert b"Setup Complete" in rv.data
    
    # Verify file write
    m.assert_called_with('.env', 'w')
    handle = m()
    handle.write.assert_called()
    content = handle.write.call_args[0][0]
    assert "DATABASE_URL=postgresql://test" in content
