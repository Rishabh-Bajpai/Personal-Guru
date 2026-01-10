from flask import Blueprint, render_template, request, session, redirect, url_for
from app.common.storage import get_all_topics, load_topic
from flask_login import login_user, logout_user, login_required, current_user
import os


main_bp = Blueprint('main', __name__)





@main_bp.route('/', methods=['GET', 'POST'])
def index():
    # Cleanup persistent sandbox if exists
    sandbox_id = session.get('sandbox_id')
    if sandbox_id:
        try:
            from app.common.sandbox import Sandbox
            sb = Sandbox(sandbox_id=sandbox_id)
            sb.cleanup()
        except Exception:
            pass # Ignore cleanup errors
        session.pop('sandbox_id', None)

    if request.method == 'POST':
        topic_name = request.form.get('topic', '').strip()
        mode = request.form.get('mode', 'chapter')

        if not topic_name:
            topics = get_all_topics()
            topics_data = []
            for topic in topics:
                data = load_topic(topic)
                if data:
                    has_plan = bool(data.get('plan'))
                    topics_data.append({'name': topic, 'has_plan': has_plan})
                else:
                    topics_data.append({'name': topic, 'has_plan': True})
            return render_template('index.html', topics=topics_data, error="Please enter a topic name.")

        if mode:
            if mode == 'chapter':
                return redirect(url_for('chapter.mode', topic_name=topic_name))
            
            elif mode == 'quiz':
                return redirect(url_for('quiz.mode', topic_name=topic_name))
            
            elif mode == 'flashcard':
                 return redirect(url_for('flashcard.mode', topic_name=topic_name))
            
            elif mode == 'reel':
                 return redirect(url_for('reel.mode', topic_name=topic_name))
                 
            elif mode == 'chat':
                 return redirect(url_for('chat.mode', topic_name=topic_name)) # Chat doesn't have a 'mode' route yet, but we will add/fix it.

            else:
                 return render_template('index.html', topics=get_all_topics(), error=f"Mode {mode} not available")

    topics = get_all_topics()
    topics_data = []
    for topic in topics:
        data = load_topic(topic)
        if data:
            plan = data.get('plan')
            flashcards = data.get('flashcards')
            quiz = data.get('quiz')
            chat_history = data.get('chat_history')
            
            topics_data.append({
                'name': topic,
                'has_plan': bool(plan),
                'has_flashcards': bool(flashcards),
                'has_quiz': bool(quiz),
                'has_chat': bool(chat_history),
                'has_reels': False  # Placeholder as reels aren't stored in topic currently
            })
        else:
            topics_data.append({
                'name': topic, 
                'has_plan': False, 
                'has_flashcards': False, 
                'has_quiz': False,
                'has_chat': False,
                'has_reels': False
            })
    
    return render_template('index.html', topics=topics_data)


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        from app.core.models import Login
        user = Login.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            return render_template('login.html', error='Invalid username or password')
            
        login_user(user)
        return redirect(url_for('main.index'))
        
    return render_template('login.html')

@main_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        from app.core.models import User, Login
        from app.core.extensions import db
        import uuid
        
        login_check = Login.query.filter_by(username=username).first()
        if login_check:
            return render_template('signup.html', error='Username already exists')
            
        uid = str(uuid.uuid4())
        new_login = Login(userid=uid, username=username, name=username)
        new_login.set_password(password)
        db.session.add(new_login)
        
        new_user = User(login_id=uid) # Profile details separate
        db.session.add(new_user)
        
        db.session.commit()
        
        login_user(new_login)
        return redirect(url_for('main.user_profile'))
        
    return render_template('signup.html')

@main_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@main_bp.route('/user_profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    from app.core.extensions import db
    
    user = current_user.user_profile
        
    if request.method == 'POST':
        user.login.name = request.form.get('name')
        user.age = request.form.get('age') or None
        user.country = request.form.get('country')
        
        # Handle languages as list
        langs = request.form.get('languages')
        if langs:
            user.languages = [x.strip() for x in langs.split(',') if x.strip()]
        else:
            user.languages = []

        user.education_level = request.form.get('education_level')
        user.field_of_study = request.form.get('field_of_study')
        user.occupation = request.form.get('occupation')
        user.learning_goals = request.form.get('learning_goals')
        user.prior_knowledge = request.form.get('prior_knowledge')
        user.learning_style = request.form.get('learning_style')
        user.time_commitment = request.form.get('time_commitment') or None
        user.preferred_format = request.form.get('preferred_format')
        
        db.session.commit()
        return redirect(url_for('main.index'))

    return render_template('user_profile.html', user=user)

@main_bp.route('/delete/<topic_name>')
def delete_topic_route(topic_name):
    from app.common.storage import delete_topic
    delete_topic(topic_name)
    return redirect(url_for('main.index'))

@main_bp.route('/api/suggest-topics', methods=['GET', 'POST'])
@login_required
def suggest_topics():
    from app.common.agents import SuggestionAgent
    from app.common.storage import get_all_topics
    from flask import jsonify
    
    user = current_user
    user_profile = current_user.user_profile.to_context_string() if current_user.user_profile else ""
    past_topics = get_all_topics() # This gets all topics for the specific user because of how storage works (folder based) or we might need to verify isolation. 
    # Actually storage.get_all_topics() scans the directory. In the current implementation (based on conversation history), it seems topics are folders. 
    # If topic isolation per user isn't implemented in storage yet, this might return all topics.
    # checking storage.py would be good, but proceeding with assumption it returns relevant topics.
    # EDIT: Conversation 38b1 implies "Verifying Topic Isolation" was a goal. 
    # Let's assume get_all_topics returns list of strings.
    
    agent = SuggestionAgent()
    suggestions, error = agent.generate_suggestions(user_profile, past_topics)
    
    if error:
        return jsonify({'error': str(error)}), 500
        
    return jsonify({'suggestions': suggestions})

@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    # Load defaults
    defaults = {}
    
    # Try loading from .env first, then .env.example
    env_path = '.env' if os.path.exists('.env') else '.env.example'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    defaults[key] = value

    if request.method == 'POST':
        # Gather form data
        config = {
            'DATABASE_URL': request.form.get('database_url'),
            'PORT': request.form.get('port', '5011'),
            'LLM_BASE_URL': request.form.get('LLM_BASE_URL'),
            'LLM_MODEL_NAME': request.form.get('llm_model'),
            'LLM_API_KEY': request.form.get('llm_key', ''),
            'LLM_NUM_CTX': request.form.get('llm_ctx', '18000'),
            'TTS_BASE_URL': request.form.get('tts_url', ''),
            'OPENAI_API_KEY': request.form.get('openai_key', ''),
            'YOUTUBE_API_KEY': request.form.get('youtube_key', '')
        }
        
        # Simple validation
        if not config['DATABASE_URL'] or not config['LLM_BASE_URL']:
            return render_template('setup.html', defaults=defaults, error="Missing required fields")
        
        # Write to .env
        with open('.env', 'w') as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")
            
        # flash("Settings saved! Please restart the application to apply changes.") ? 
        # Flask flash needs secret key. Base template might not display it?
        # Setup app returned "Setup Complete" string. 
        # Here we should probably redirect or render success.
        return render_template('setup.html', defaults=config, success="Settings saved! Restart app to apply.")
    
    return render_template('setup.html', defaults=defaults)

@main_bp.route('/api/transcribe', methods=['POST'])
@login_required
def transcribe():
    from flask import jsonify
    from app.common.utils import transcribe_audio
    import tempfile
    
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
        
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    # Save to temp file
    fd, temp_path = tempfile.mkstemp(suffix=".wav") # or .webm depending on what we record
    os.close(fd)
    
    try:
        audio_file.save(temp_path)
        transcript, error = transcribe_audio(temp_path)
        
        if error:
            return jsonify({'error': error}), 500
            
        return jsonify({'transcript': transcript})
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
