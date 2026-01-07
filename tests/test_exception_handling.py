
import pytest
from unittest.mock import patch, MagicMock
from app.core.exceptions import LLMResponseError, TopicNotFoundError, DatabaseError, ValidationError
import json

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

def test_llm_error_handling(client_no_auth, app):
    """Test that LLM errors are caught by global handler and return 503."""
    # Patch flask_login user loader or ensure bypass works
    # LOGIN_DISABLED prevents login_required, but some routes access current_user attributes.
    # We must patch current_user where it is used.
    
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.username = 'testuser'
    
    with patch('flask_login.utils._get_user', return_value=mock_user), \
         patch('app.common.storage.current_user', mock_user):
        
        # Use Chapter route which bubles up exceptions
        # Patch the class method to ensure it catches all instances
        with patch('app.common.agents.PlannerAgent.generate_study_plan') as mock_planner:
            mock_planner.side_effect = LLMResponseError(
                "Service Down",
                error_code="LLM503",
                user_message="AI Service is currently unavailable.",
                should_retry=True
            )
            
            with patch('app.common.utils.get_user_context', return_value="Beginner"):
                response = client_no_auth.post('/chapter/generate', 
                                     json={"topic": "TestTopic"},
                                     headers={"Content-Type": "application/json"},
                                     follow_redirects=False)
                
                assert response.status_code == 503
                # Check for error code or partial message to avoid HTML escaping issues
                assert b"AI Service is currently unavailable" in response.data or b"LLM503" in response.data

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

