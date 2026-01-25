import pytest
from app import create_app
from app.common.auth import create_jwe, decrypt_jwe
from app.core.models import Login

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier API testing
    app.config['SECRET_KEY'] = 'test-secret-key-very-long-enough-for-sha256'

    # Setup DB
    with app.app_context():
        from app.core.extensions import db
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_jwe_helpers(app):
    """Test Create and Decrypt JWE helpers (unchanged)."""
    with app.app_context():
        payload = {'user_id': 'test_user'}
        token = create_jwe(payload)
        assert token is not None
        assert isinstance(token, bytes)

        decrypted = decrypt_jwe(token)
        assert decrypted == payload

def test_login_does_not_set_cookie(client, app):
    """Test that login response does NOT set JWE cookie anymore."""
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u1', username='test', installation_id='i1')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    response = client.post('/login', data={'username': 'test', 'password': 'pass'}, follow_redirects=False)
    assert response.status_code == 302

    # Verify NO Set-Cookie for jwe_token
    cookie_header = None
    for header in response.headers:
        if header[0] == 'Set-Cookie' and 'jwe_token=' in header[1]:
            cookie_header = header[1]
            break

    assert cookie_header is None, "JWE Cookie should NOT be set in response headers"

def test_protected_route_requires_jwe_header(client, app):
    """Test that state-changing routes fail without JWE header and pass with it."""
    # Create and login user
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u1', username='test', installation_id='i1')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    client.post('/login', data={'username': 'test', 'password': 'pass'})

    # Generate a valid token manually (since we can't easily grab it from context in a POST test without parsing html)
    with app.app_context():
        token_bytes = create_jwe({'user_id': 'u1'})
        valid_token = token_bytes.decode('utf-8')

    # 1. Request WITHOUT Header -> Should Fail
    response = client.post('/api/feedback', json={
        'feedback_type': 'general_feedback',
        'rating': 5,
        'comment': 'Good'
    })
    # Should fail with 401
    assert response.status_code == 401
    assert b"Missing Security Token" in response.data or b"Missing X-JWE-Token" in response.data

    # 2. Request WITH Header -> Should Succeed
    response = client.post('/api/feedback',
        json={'feedback_type': 'general_feedback', 'rating': 5, 'comment': 'Good'},
        headers={'X-JWE-Token': valid_token}
    )
    assert response.status_code == 200

def test_global_enforcement_on_other_blueprints(client, app):
    """Test that JWE is enforced on blueprints other than main (e.g. Chapter)."""
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u1', username='test', installation_id='i1')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    client.post('/login', data={'username': 'test', 'password': 'pass'})

    with app.app_context():
        token_bytes = create_jwe({'user_id': 'u1'})
        valid_token = token_bytes.decode('utf-8')

    # 1. Access Chapter route WITHOUT token
    response = client.post('/chapter/generate', json={'topic': 'test'})
    assert response.status_code == 401

    # 2. Access Chapter route WITH token
    # Note: Using a valid token, we expect it to pass auth check.
    # Whatever happens next (400, 500, 200) means auth passed.
    response = client.post('/chapter/generate',
        json={'topic': 'test'},
        headers={'X-JWE-Token': valid_token}
    )
    assert response.status_code != 401

def test_tampered_jwe_header(client, app):
    """Test that tampered JWE header fails."""
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u1', username='test', installation_id='i1')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    client.post('/login', data={'username': 'test', 'password': 'pass'})

    response = client.post('/api/feedback',
        json={'feedback_type': 'general_feedback', 'rating': 5, 'comment': 'Good'},
        headers={'X-JWE-Token': 'invalid.token.string'}
    )
    assert response.status_code == 401 or response.status_code == 422

def test_jwe_in_form_data(client, app):
    """Test that JWE can be passed in form data (fallback for standard POST)."""
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u1', username='test', installation_id='i1')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    client.post('/login', data={'username': 'test', 'password': 'pass'})

    with app.app_context():
        token_bytes = create_jwe({'user_id': 'u1'})
        valid_token = token_bytes.decode('utf-8')

    # 1. Request WITHOUT header OR form field -> Fail
    response = client.post('/api/feedback', data={'feedback_type': 'general_feedback'})
    assert response.status_code == 401

    # 2. Request WITH form field -> Succeed
    # Note: /api/feedback expects JSON usually but routes.py checks auth BEFORE parsing body type
    # So if we send form data, the auth check runs.
    # Logic: request.form populated? YES if content-type is form-urlencoded.
    response = client.post('/api/feedback',
        data={
            'feedback_type': 'general_feedback',
            'rating': 5,
            'comment': 'Good',
            'jwe_token': valid_token
        }
    )
    # It might fail 400 because /api/feedback expects JSON body, but Auth (401) should pass.
    # If we get 400, it means we passed Auth!
    assert response.status_code != 401, f"Auth should pass with form data. Got {response.status_code}"

def test_jwe_in_json_body(client, app):
    """Test that JWE can be passed in JSON body (fallback for JSON POST)."""
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u1', username='test', installation_id='i1')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    client.post('/login', data={'username': 'test', 'password': 'pass'})

    with app.app_context():
        token_bytes = create_jwe({'user_id': 'u1'})
        valid_token = token_bytes.decode('utf-8')

    # Request WITH JSON field -> Succeed
    response = client.post('/api/feedback',
        json={
            'feedback_type': 'general_feedback',
            'rating': 5,
            'comment': 'Good',
            'jwe_token': valid_token
        }
    )
    assert response.status_code == 200

def test_jwe_injection_in_templates(client, app):
    """Test that JWE token is injected into templates (global context, specifically testing chapter blueprint)."""
    with app.app_context():
        from app.core.extensions import db
        u = Login(userid='u2', username='user2', installation_id='i2')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

    client.post('/login', data={'username': 'user2', 'password': 'pass'})

    # We must save topic AFTER login so it goes to user folder if user isolation is active
    # (Though current storage might be shared or based on session, let's just do it in a request context if needed)
    # Actually save_topic relies on current_user? Let's check imports.
    # It imports current_user inside the function usually.
    # So we need to fake login or push context.

    # Simpler: The `client` cookie jar has the session.
    # But for backend `save_topic` to work, `current_user` proxy must point to user.
    # This requires a test_request_context with the cookie?

    # Alternative: JWE Check on /settings (which is main_bp, but we want to test global).
    # Wait, /settings IS main_bp. The bug fixed was that main_bp context processor worked for main_bp routes but NOT chapter_bp.
    # So testing /settings proves nothing new.
    # We MUST tests a route NOT in main_bp.
    # /quiz/<topic> or /chapter/<topic>.

    # Let's try to mock `load_topic` in the route?
    # Or just use the fact that `login_required` redirects to login if not logged in.
    # If logged in, we hit the route.

    # Let's blindly try to save the topic.
    # Note: save_topic writes to disk.

    with client.session_transaction() as sess:
        sess['_user_id'] = 'u2' # Force login in session

    # We still need to create the topic.
    # Let's cheat and mock `load_topic` to return data without disk IO
    from unittest.mock import patch
    with patch('app.modes.chapter.routes.load_topic') as mock_load:
        mock_load.return_value = {
            'name': 'TestJWE',
            'plan': ['Step 1'],
            'chapter_mode': [{'title': 'Step 1', 'teaching_material': 'Content', 'questions': None}]
        }

        # We hit the learn page directly
        response = client.get('/chapter/learn/TestJWE/0')
        assert response.status_code == 200

        content = response.data.decode('utf-8')

        # Check for meta tag
        import re
        # Look for <meta name="jwe-token" content="...">
        match = re.search(r'<meta name="jwe-token" content="([^"]+)">', content)
        assert match, "JWE Meta tag not found in Chapter template"
        token = match.group(1)
        assert token and token.strip() != '', "JWE Token is empty"

def test_jwe_identity_verification(client, app):
    """Test that a JWE token from one user cannot be used by another."""
    with app.app_context():
        from app.core.extensions import db
        # Create two distinct users
        u1 = Login(userid='user_a', username='usera', installation_id='i1')
        u1.set_password('pass')
        u2 = Login(userid='user_b', username='userb', installation_id='i1')
        u2.set_password('pass')
        db.session.add_all([u1, u2])
        db.session.commit()

    # 1. Login as User A to generate a valid token
    client.post('/login', data={'username': 'usera', 'password': 'pass'})

    with app.app_context():
        token_bytes = create_jwe({'user_id': 'user_a'})
        token_a = token_bytes.decode('utf-8')

    # Logout User A
    client.get('/logout')

    # 2. Login as User B
    client.post('/login', data={'username': 'userb', 'password': 'pass'})

    # 3. Attempt to use Token A while logged in as User B
    response = client.post('/api/feedback',
        json={'feedback_type': 'general_feedback', 'rating': 5, 'comment': 'Good'},
        headers={'X-JWE-Token': token_a}
    )

    # Should be 403 Forbidden (Identity Mismatch)
    assert response.status_code == 403
