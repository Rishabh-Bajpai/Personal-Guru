import sys
import os
import unittest
from flask import Flask

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.common.models import Topic, StudyStep, User
from app.core.storage import load_topic, save_topic, save_chat_history
from unittest.mock import patch
from config import Config

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'test.db')

class TestChatPersistence(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create test user
        self.user = User(username="testuser", name="Test User")
        self.user.set_password("password")
        db.session.add(self.user)
        db.session.commit()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(basedir, 'test.db')
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_chat_mode_persistence(self):
        with self.app.test_client() as client:
            login_resp = client.post('/login', data={'username': 'testuser', 'password': 'password'})
            # Verify login didn't fail (usually login success redirects to index or next)
            if login_resp.status_code == 200 and b'Login' in login_resp.data:
                 print("DEBUG: Login Failed (Form returned)")
            elif login_resp.status_code == 302:
                 # Check location. If it stays on /auth/login or goes to /login, bad.
                 loc = login_resp.headers.get('Location')
                 print(f"DEBUG: Login Redirect to: {loc}")
            
            topic_name = "Test Topic"
            
            # 1. Initialize Topic (via visit or manual DB insert for speed)
            # Just insert DB object to avoid agent calls in 'mode' route
            t = Topic(name=topic_name, user_id="testuser")
            t.chat_history = [{"role": "assistant", "content": "Welcome"}]
            db.session.add(t)
            db.session.commit()
            
            # 2. Send Message via Route
            # We mock the ChatModeMainChatAgent instance in routes
            with patch('app.modes.chat.routes.chat_agent.get_answer') as mock_agent:
                mock_agent.return_value = ("I am a bot", None)
                
                response = client.post(f'/chat/{topic_name}/send', data={'message': 'Hello Bot'})
                if response.status_code != 302:
                    print(f"DEBUG: Chat Mode Response: {response.data}")
                else:
                    print(f"DEBUG: Chat Mode Redirect to: {response.headers.get('Location')}")
                self.assertEqual(response.status_code, 302) # Redirects back
            
            # 3. Verify DB
            db.session.remove() # Force clean session/transaction
            print(f"DEBUG: Test Engine: {db.engine.url}")
            from sqlalchemy import text
            with db.engine.connect() as conn:
                 result = conn.execute(text("SELECT chat_history FROM topics")).fetchall()
                 print(f"DEBUG: RAW DB CONTENT: {result}")
            
            t_updated = Topic.query.filter_by(name=topic_name).first()
            if len(t_updated.chat_history) != 3:
                print(f"DEBUG: Chat History: {t_updated.chat_history}")
            self.assertEqual(len(t_updated.chat_history), 3) # Welcome, User, Assistant
            self.assertEqual(t_updated.chat_history[1]['content'], "Hello Bot")
            self.assertEqual(t_updated.chat_history[2]['content'], "I am a bot")

    def test_chapter_mode_persistence(self):
        with self.app.test_client() as client:
            client.post('/login', data={'username': 'testuser', 'password': 'password'})
            
            # 1. Create Topic with Steps
            topic_name = "Chapter Topic"
            t = Topic(name=topic_name, user_id="testuser")
            t.study_plan = ["Step 1", "Step 2"]
            
            # Create Steps manually
            s1 = StudyStep(topic=t, step_index=0, title="Step 1", content="Content 1")
            s2 = StudyStep(topic=t, step_index=1, title="Step 2", content="Content 2")
            
            db.session.add(t)
            db.session.add(s1)
            db.session.add(s2)
            db.session.commit()
            
            # 2. Send Message to Step 0 via Route
            # Route: /chat/<topic_name>/<int:step_index> (POST json)
            # note: in routes.py it is @chat_bp.route('/<topic_name>/<int:step_index>', methods=['POST'])
            # but usually blueprint prefix is /chat.
            # Wait, verify endpoint URL. 
            # In app/__init__.py or app/modes/chat/__init__.py?
            
            # Let's assume /chat prefix based on test_chat_mode_persistence success assumption.
            
            # 2. Send Message to Step 0 via Route
            
            # We mock the ChapterModeChatAgent instance in routes
            with patch('app.modes.chat.routes.chapter_agent.get_answer') as mock_agent:
                mock_agent.return_value = ("Step Answer", None)
                
                response = client.post(f'/chat/{topic_name}/0', json={'question': 'Question about step 1'})
                if response.status_code != 200:
                     print(f"DEBUG: Chapter Mode Status: {response.status_code}, Location: {response.headers.get('Location')}")
                     print(f"DEBUG: Chapter Mode Data: {response.data}")
                     
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['answer'], "Step Answer")
            
            # 3. Verify Persistence in DB (Step 0)
            db.session.expire_all()
            step_0_db = StudyStep.query.filter_by(topic_id=t.id, step_index=0).first()
            self.assertEqual(len(step_0_db.chat_history), 2) # User, Assistant
            self.assertEqual(step_0_db.chat_history[0]['content'], "Question about step 1")
            self.assertEqual(step_0_db.chat_history[1]['content'], "Step Answer")
            
            # 4. Verify Step 1 is empty
            step_1_db = StudyStep.query.filter_by(topic_id=t.id, step_index=1).first()
            self.assertFalse(step_1_db.chat_history)

if __name__ == '__main__':
    unittest.main()
