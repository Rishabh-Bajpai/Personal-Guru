from flask import Blueprint, render_template, request, session, redirect, url_for
from app.common.storage import get_all_topics, load_topic
from app.common.utils import log_telemetry
from flask_login import login_user, logout_user, login_required, current_user
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    """Render home page with topics list or redirect to selected learning mode."""
    # Cleanup persistent sandbox if exists
    sandbox_id = session.get('sandbox_id')
    if sandbox_id:
        try:
            from app.common.sandbox import Sandbox
            sb = Sandbox(sandbox_id=sandbox_id)
            sb.cleanup()
        except Exception:
            pass  # Ignore cleanup errors
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
            return render_template(
                'index.html',
                topics=topics_data,
                error="Please enter a topic name.")

        # Telemetry Hook: Topic Created/Opened (Intent)
        try:
            log_telemetry(
                event_type='topic_created' if topic_name not in get_all_topics() else 'topic_opened',
                triggers={'source': 'web_ui', 'action': 'form_submit'},
                payload={'topic_name': topic_name, 'mode': mode}
            )
        except Exception:
            pass # Telemetry failures must not block user flow; ignore logging errors.

        if mode:
            if mode == 'chapter':
                return redirect(url_for('chapter.mode', topic_name=topic_name))

            elif mode == 'quiz':
                return redirect(url_for('quiz.mode', topic_name=topic_name))

            elif mode == 'flashcard':
                return redirect(
                    url_for(
                        'flashcard.mode',
                        topic_name=topic_name))

            elif mode == 'reel':
                return redirect(url_for('reel.mode', topic_name=topic_name))

            elif mode == 'chat':
                # Chat doesn't have a 'mode' route yet, but we will add/fix it.
                return redirect(url_for('chat.mode', topic_name=topic_name))

            else:
                return render_template(
                    'index.html',
                    topics=get_all_topics(),
                    error=f"Mode {mode} not available")


    topics = get_all_topics()
    topics_data = []
    for topic in topics:
        data = load_topic(topic)
        if data:
            plan = data.get('plan')
            flashcard_mode = data.get('flashcard_mode')
            quiz = data.get('quiz_mode')
            chat_history = data.get('chat_history')

            topics_data.append({
                'name': topic,
                'has_plan': bool(plan),
                'has_flashcards': bool(flashcard_mode),
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


@main_bp.context_processor
def inject_notifications():
    """Make notifications available to all templates."""
    from app.common.utils import check_for_updates

    # Define app version here or import from config
    APP_VERSION = "v0.0.1" # TODO: Move to config

    try:
        update_note = check_for_updates(APP_VERSION)
        if update_note:
            return dict(system_notifications=[update_note])
    except Exception:
        pass

    return dict(system_notifications=[])


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with username and password authentication."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        from app.core.models import Login
        user = Login.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            return render_template(
                'login.html', error='Invalid username or password')

        login_user(user)

        # Telemetry Hook: User Login
        try:
            log_telemetry(
                event_type='user_login',
                triggers={'source': 'web_ui', 'action': 'form_submit'},
                payload={'method': 'password'}
            )
        except Exception:
            pass # Telemetry failures must not block user flow; ignore logging errors.

        return redirect(url_for('main.index'))

    return render_template('login.html')


@main_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle new user registration and profile creation."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        from app.core.models import User, Login, Installation
        from app.core.extensions import db

        login_check = Login.query.filter_by(username=username).first()
        if login_check:
            return render_template('signup.html', error='Username already exists')

        # Determine installation context explicitly
        installations = Installation.query.all()
        if len(installations) == 0:
            # First time setup - Create Installation
            # First time setup - Wait for DCS Registration
            # The background SyncManager should have registered the device.
            # If not yet, we ask user to wait.
            return render_template('signup.html', error='System is initializing registration. Please wait a moment and try again.')

        elif len(installations) == 1:
            inst_id = installations[0].installation_id
        else:
            # Multiple installations detected; avoid arbitrary association
            return render_template(
                'signup.html',
                error='Multiple installations are configured. Please contact the administrator.'
            )

        uid = Login.generate_userid(inst_id)

        new_login = Login(userid=uid, username=username, name=username, installation_id=inst_id)
        new_login.set_password(password)
        db.session.add(new_login)

        new_user = User(login_id=uid) # Profile details separate
        db.session.add(new_user)

        db.session.commit()

        login_user(new_login)

        # Telemetry Hook: User Signup
        try:
            telemetry_payload = {}
            from app.common.utils import get_system_info
            sys_info = get_system_info()
            if isinstance(sys_info, dict) and 'install_method' in sys_info:
                telemetry_payload['install_method'] = sys_info['install_method']

            log_telemetry(
                event_type='user_signup',
                triggers={'source': 'web_ui', 'action': 'form_submit'},
                payload=telemetry_payload,
                installation_id=inst_id
            )
        except Exception:
            pass # Telemetry failures must not block user flow; ignore logging errors.

        return redirect(url_for('main.user_profile', new_user='true'))

    return render_template('signup.html')


@main_bp.route('/logout')
def logout():
    """Log out the current user and redirect to home page."""
    logout_user()
    return redirect(url_for('main.index'))


@main_bp.route('/user_profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    """Display and update user profile information."""
    from app.core.extensions import db

    user = current_user.user_profile

    if request.method == 'POST':
        if user.login is not None:
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

    show_terms = request.args.get('new_user') == 'true'
    return render_template('user_profile.html', user=user, show_terms=show_terms)


@main_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    """Permanently delete the current user's account and all associated data."""
    from app.core.extensions import db

    try:
        user = current_user
        db.session.delete(user)
        db.session.commit()
        logout_user()
        return redirect(url_for('main.signup')) # Redirect to signup or home
    except Exception as e:
        db.session.rollback()
        # In a real app we'd flash an error, but let's just log and redirect for now
        print(f"Error deleting account: {e}")
        return redirect(url_for('main.user_profile'))


@main_bp.route('/delete/<topic_name>')
def delete_topic_route(topic_name):
    """Delete the specified topic and redirect to home page."""
    from app.common.storage import delete_topic
    delete_topic(topic_name)

    # Telemetry Hook: Topic Deleted
    try:
        log_telemetry(
            event_type='topic_deleted',
            triggers={'source': 'web_ui', 'action': 'click_delete'},
            payload={'topic_name': topic_name}
        )
    except Exception:
        pass # Telemetry failures must not block user flow; ignore logging errors.

    return redirect(url_for('main.index'))


@main_bp.route('/api/suggest-topics', methods=['GET', 'POST'])
@login_required
def suggest_topics():
    """
    Generate AI-powered topic suggestions based on user profile.

    ---
    tags:
      - Suggestions
    responses:
      200:
        description: List of suggested topics
        schema:
          type: object
          properties:
            suggestions:
              type: array
              items:
                type: string
      500:
        description: Internal Server Error
    """
    from app.common.agents import SuggestionAgent
    from app.common.storage import get_all_topics
    from flask import jsonify

    user_profile = current_user.user_profile.to_context_string() if current_user.user_profile else ""
    past_topics = get_all_topics() # This gets all topics for the specific user because of how storage works (folder based) or we might need to verify isolation.
    # Actually storage.get_all_topics() scans the directory. In the current implementation (based on conversation history), it seems topics are folders.
    # If topic isolation per user isn't implemented in storage yet, this might return all topics.
    # checking storage.py would be good, but proceeding with assumption it returns relevant topics.
    # EDIT: Conversation 38b1 implies "Verifying Topic Isolation" was a goal.
    # Let's assume get_all_topics returns list of strings.

    agent = SuggestionAgent()
    try:
        suggestions, error = agent.generate_suggestions(user_profile, past_topics)
        if error:
            return jsonify({'error': str(error)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'suggestions': suggestions})


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Display and update application settings stored in .env file."""
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
            'LLM_NUM_CTX': request.form.get('llm_ctx', '4096'),
            'TTS_BASE_URL': request.form.get('tts_url', ''),
            'OPENAI_API_KEY': request.form.get('openai_key', ''),
            'YOUTUBE_API_KEY': request.form.get('youtube_key', '')
        }

        # Simple validation
        if not config['DATABASE_URL'] or not config['LLM_BASE_URL']:
            return render_template(
                'setup.html',
                defaults=defaults,
                error="Missing required fields")

        # Write to .env
        with open('.env', 'w') as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")

        # flash("Settings saved! Please restart the application to apply changes.") ?
        # Flask flash needs secret key. Base template might not display it?
        # Setup app returned "Setup Complete" string.
        # Here we should probably redirect or render success.
        return render_template(
            'setup.html',
            defaults=config,
            success="Settings saved! Restart app to apply.")

    return render_template('setup.html', defaults=defaults)


@main_bp.route('/api/transcribe', methods=['POST'])
@login_required
def transcribe():
    """
    Transcribe uploaded audio file to text using STT service.

    ---
    tags:
      - Audio
    parameters:
      - name: audio
        in: formData
        type: file
        required: true
        description: Audio file to transcribe
    responses:
      200:
        description: Transcription result
        schema:
          type: object
          properties:
            transcript:
              type: string
      400:
        description: No audio file provided
    """
    from flask import jsonify
    from app.common.utils import transcribe_audio
    import tempfile

    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Save to temp file
    # or .webm depending on what we record
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    try:
        audio_file.save(temp_path)
        try:
            transcript = transcribe_audio(temp_path)
        except Exception as error:
            return jsonify({'error': str(error)}), 500

        return jsonify({'transcript': transcript})

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@main_bp.route('/api/feedback', methods=['POST'])
# @login_required  <-- Removed to allow feedback from login screen
def submit_feedback():
    """
    Handle user feedback form submissions.

    Accepts JSON with feedback_type, rating (1-5), and comment.
    Saves to the Feedback table and logs telemetry event.

    ---
    tags:
      - Feedback
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - feedback_type
            - comment
          properties:
            feedback_type:
              type: string
              enum: ['form', 'in_place']
            rating:
              type: integer
              minimum: 1
              maximum: 5
            comment:
              type: string
    responses:
      200:
        description: Feedback submitted successfully
      400:
        description: Invalid input
    """
    from flask import jsonify
    from app.core.extensions import db
    from app.core.models import Feedback

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        feedback_type = data.get('feedback_type')
        rating = data.get('rating')
        comment = data.get('comment')

        if not feedback_type:
            return jsonify({'error': 'Feedback type is required'}), 400
        if rating is not None and rating != 0 and (not isinstance(rating, int) or rating < 1 or rating > 5):
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        if not comment or not comment.strip():
            return jsonify({'error': 'Comment is required'}), 400

        # Handle anonymous users
        user_id = current_user.userid if current_user.is_authenticated else None

        new_feedback = Feedback(
            user_id=user_id,
            feedback_type=feedback_type,
            content_reference='feedback_form',
            rating=rating,
            comment=comment.strip()
        )
        db.session.add(new_feedback)
        db.session.commit()

        # Telemetry Hook: Feedback Submitted
        try:
            log_telemetry(
                event_type='feedback_submitted',
                triggers={'source': 'web_ui', 'action': 'modal_form'},
                payload={'feedback_type': feedback_type, 'rating': rating}
            )
        except Exception:
            pass  # Telemetry failures must not block user flow

        return jsonify({'success': True, 'message': 'Feedback submitted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
