import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from app import app as flask_app
import json

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

def test_home_page(client, mocker):
    """Test that the home page loads correctly."""
    mocker.patch('app.get_all_topics', return_value=[])
    response = client.get('/')
    assert response.status_code == 200
    assert b"What would you like to learn today?" in response.data

def test_full_learning_flow(client, mocker):
    """Test the full user flow from topic submission to finishing the course."""
    topic_name = "testing"

    # Mock PlannerAgent
    mocker.patch('src.agents.PlannerAgent.generate_study_plan', return_value=(['Step 1', 'Step 2'], None))

    # Mock TopicTeachingAgent
    mocker.patch('src.agents.TopicTeachingAgent.generate_teaching_material', return_value=("## Step Content", None))

    # Mock AssessorAgent
    mocker.patch('src.agents.AssessorAgent.generate_question', return_value=({
        "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": "A"}]
    }, None))

    # Mock storage functions
    mocker.patch('app.load_topic', return_value=None)
    mocker.patch('app.save_topic', return_value=None)

    # 1. User submits a new topic
    response = client.post('/', data={'topic': topic_name})
    assert response.status_code == 302
    assert response.headers['Location'] == f'/learn/{topic_name}/0'

    # Mock storage.load_topic to return the created topic data
    topic_data = {
        "name": topic_name,
        "plan": ["Step 1", "Step 2"],
        "steps": [
            {},
            {}
        ]
    }
    mocker.patch('app.load_topic', return_value=topic_data)

    # 2. User follows the redirect to the first learning step
    response = client.get(f'/learn/{topic_name}/0')
    assert response.status_code == 200
    assert b"Step 1" in response.data
    assert b'<div id="step-content-markdown" style="display: none;">## Step Content</div>' in response.data

    # 3. User submits an answer
    topic_data['steps'][0] = {"teaching_material": "## Step Content", "questions": {"questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": "A"}]}}
    mocker.patch('app.load_topic', return_value=topic_data)
    response = client.post(f'/assess/{topic_name}/0', data={'option_0': 'A'})
    assert response.status_code == 200
    assert b"Your Score: 100.0%" in response.data

    # 4. User continues to the next step
    topic_data['steps'][0]['user_answers'] = ['A']
    topic_data['steps'][0]['completed'] = True
    mocker.patch('app.load_topic', return_value=topic_data)
    response = client.get(f'/learn/{topic_name}/1')
    assert response.status_code == 200
    assert b"Check Your Understanding" in response.data # Check that assessment is shown

    # 5. User goes back to the previous step
    response = client.get(f'/learn/{topic_name}/0')
    assert response.status_code == 200
    assert b"Check Your Understanding" in response.data
    assert b'action="/assess/testing/0"' not in response.data # Check that assessment form is not shown

    # 6. User finishes the course
    topic_data['steps'][1] = {"teaching_material": "## Step 2 Content", "questions": {"questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": "C"}]}}
    mocker.patch('app.load_topic', return_value=topic_data)
    response = client.post(f'/assess/{topic_name}/1', data={'option_0': 'C'})
    assert response.status_code == 302
    assert response.headers['Location'] == f'/complete/{topic_name}'

    # 7. User sees the completion page
    response = client.get(f'/complete/{topic_name}')
    assert response.status_code == 200
    assert b"Congratulations!" in response.data

def test_export_topic(client, mocker):
    """Test the export functionality."""
    topic_name = "export_test"
    topic_data = {
        "name": topic_name,
        "plan": ["Step 1"],
        "steps": [{"teaching_material": "## Test Content"}]
    }
    mocker.patch('app.load_topic', return_value=topic_data)

    response = client.get(f'/export/{topic_name}')
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == f'attachment; filename={topic_name}.md'
    assert response.data == b'# export_test\n\n## Step 1\n\n## Test Content\n\n'

def test_delete_topic(client, mocker):
    """Test deleting a topic."""
    topic_name = "delete_test"
    mocker.patch('app.get_all_topics', return_value=[topic_name])

    # Check that the topic is listed
    response = client.get('/')
    assert bytes(topic_name, 'utf-8') in response.data

    # Delete the topic
    mocker.patch('app.delete_topic', return_value=None)
    response = client.get(f'/delete/{topic_name}')
    assert response.status_code == 302
    assert response.headers['Location'] == '/'

    # Check that the topic is no longer listed
    mocker.patch('app.get_all_topics', return_value=[])
    response = client.get('/')
    assert bytes(topic_name, 'utf-8') not in response.data

def test_chat_route(client, mocker):
    """Test the /chat route."""
    topic_name = "chat_test"
    step_index = 0
    topic_data = {
        "name": topic_name,
        "plan": ["Step 1"],
        "steps": [{"teaching_material": "## Test Content"}]
    }
    mocker.patch('app.load_topic', return_value=topic_data)
    mocker.patch('src.agents.ChatAgent.get_answer', return_value=("This is the answer.", None))

    response = client.post(f'/chat/{topic_name}/{step_index}', json={'question': 'hello world'})
    assert response.status_code == 200
    assert response.json == {'answer': 'This is the answer.'}
