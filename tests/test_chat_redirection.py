import pytest
from flask import url_for

def test_chat_mode_redirection(client):
    """Test that the chat mode redirection URL resolves correctly."""
    # We use the test_request_context to test url_for without a full request
    with client.application.test_request_context():
        url = url_for('chat.mode', topic_name='test_topic')
        assert url == '/chat/test_topic'

def test_chat_mode_access(auth_client, mocker):
    """Test accessing the chat mode route."""
    topic_name = "test_chat_access"

    # Mock dependencies to avoid actual DB/LLM calls
    # Mock PlannerAgent
    mocker.patch('app.modes.chat.routes.PlannerAgent.generate_study_plan', return_value=['Step 1'])

    # Also mock ChatModeMainChatAgent for welcome message
    mocker.patch('app.modes.chat.routes.ChatModeMainChatAgent.get_welcome_message', return_value="Welcome!")

    mocker.patch('app.modes.chat.routes.load_topic', return_value={"name": topic_name})
    mocker.patch('app.modes.chat.routes.save_topic')
    mocker.patch('app.modes.chat.routes.save_chat_history')

    response = auth_client.get(f'/chat/{topic_name}')
    assert response.status_code == 200
    assert b"Welcome!" in response.data
