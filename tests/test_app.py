import pytest

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
