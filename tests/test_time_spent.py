import pytest
from app.core.models import Topic, User, db
from app.common.storage import save_topic, load_topic, save_chat_history
from unittest.mock import patch

@pytest.mark.integration
def test_time_spent_persistence(app, logger):
    """Test that time_spent is correctly saved and loaded for all modes."""
    logger.section("test_time_spent_persistence")
    
    with app.app_context():
        # Ensure user exists
        if not User.query.get('time_user'):
            u = User(username='time_user')
            u.set_password('password')
            db.session.add(u)
            db.session.commit()
            
        with patch('app.common.storage.current_user') as mock_user:
            mock_user.is_authenticated = True
            mock_user.username = 'time_user'
            
            topic_name = "Time Tracking Test"
            
            # 1. Test save_topic with time_spent
            data = {
                "plan": ["Step 1"],
                "steps": [
                    {
                        "step_index": 0,
                        "title": "Step 1",
                        "content": "Content",
                        "time_spent": 120 # 2 minutes
                    }
                ],
                "quiz": {
                    "questions": [],
                    "score": 100,
                    "time_spent": 300 # 5 minutes
                },
                "flashcards": [
                    {
                        "term": "T1",
                        "definition": "D1",
                        "time_spent": 60 # 1 minute
                    }
                ],
                "last_quiz_result": {}
            }
            
            save_topic(topic_name, data)
            logger.step("Saved topic data with time_spent.")
            
            # Verify DB for Topic-related modes
            t = Topic.query.filter_by(name=topic_name).first()
            assert t is not None
            
            # Check Step
            assert len(t.steps) == 1
            assert t.steps[0].time_spent == 120
            logger.info("Step time_spent verified in DB.")
            
            # Check Quiz
            assert len(t.quizzes) == 1
            assert t.quizzes[0].time_spent == 300
            logger.info("Quiz time_spent verified in DB.")
            
            # Check Flashcard
            assert len(t.flashcards) == 1
            assert t.flashcards[0].time_spent == 60
            logger.info("Flashcard time_spent verified in DB.")
            
            # 2. Test save_chat_history with time_spent
            history = [{"role": "user", "content": "Hi"}]
            # First save without time
            save_chat_history(topic_name, history) 
            # Then add time
            save_chat_history(topic_name, history, time_spent=45)
            
            # Verify DB for Chat
            assert t.chat_mode is not None
            assert t.chat_mode.time_spent == 45
            logger.info("Chat time_spent verified in DB (initial).")
            
            # Add more time
            save_chat_history(topic_name, history, time_spent=15)
            db.session.refresh(t.chat_mode)
            assert t.chat_mode.time_spent == 60 # 45 + 15
            logger.info("Chat time_spent accumulation verified in DB.")
            
            # 3. Test load_topic
            loaded_data = load_topic(topic_name)
            
            assert loaded_data['steps'][0]['time_spent'] == 120
            assert loaded_data['quiz']['time_spent'] == 300
            assert loaded_data['flashcards'][0]['time_spent'] == 60
            assert loaded_data['chat_time_spent'] == 60
            
            logger.info("All time_spent fields verified in load_topic.")
