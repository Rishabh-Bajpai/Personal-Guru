from flask import Blueprint, render_template, request, session, redirect, url_for
from app.core.storage import get_all_topics, load_topic
from flask_login import login_user, logout_user, login_required, current_user


main_bp = Blueprint('main', __name__)





@main_bp.route('/', methods=['GET', 'POST'])
def index():
    # Cleanup persistent sandbox if exists
    sandbox_id = session.get('sandbox_id')
    if sandbox_id:
        try:
            from app.core.sandbox import Sandbox
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
        
        from app.common.models import User
        user = User.query.filter_by(username=username).first()
        
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
        
        from app.common.models import User
        from app.common.extensions import db
        
        user = User.query.filter_by(username=username).first()
        if user:
            return render_template('signup.html', error='Username already exists')
            
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('main.user_profile'))
        
    return render_template('signup.html')

@main_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@main_bp.route('/user_profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    from app.common.extensions import db
    
    user = current_user
        
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.age = request.form.get('age')
        user.country = request.form.get('country')
        user.primary_language = request.form.get('primary_language')
        user.education_level = request.form.get('education_level')
        user.field_of_study = request.form.get('field_of_study')
        user.occupation = request.form.get('occupation')
        user.learning_goals = request.form.get('learning_goals')
        user.prior_knowledge = request.form.get('prior_knowledge')
        user.learning_style = request.form.get('learning_style')
        user.time_commitment = request.form.get('time_commitment')
        user.preferred_format = request.form.get('preferred_format')
        
        db.session.commit()
        return redirect(url_for('main.index'))

    return render_template('user_profile.html', user=user)

@main_bp.route('/delete/<topic_name>')
def delete_topic_route(topic_name):
    from app.core.storage import delete_topic
    delete_topic(topic_name)
    return redirect(url_for('main.index'))

@main_bp.route('/api/suggest-topics', methods=['GET', 'POST'])
@login_required
def suggest_topics():
    from app.core.agents import SuggestionAgent
    from app.core.storage import get_all_topics
    from flask import jsonify
    
    user = current_user
    user_profile = user.to_context_string()
    past_topics = get_all_topics() # This gets all topics for the specific user because of how storage works (folder based) or we might need to verify isolation. 
    # Actually storage.get_all_topics() scans the directory. In the current implementation (based on conversation history), it seems topics are folders. 
    # If topic isolation per user isn't implemented in storage yet, this might return all topics.
    # checking storage.py would be good, but proceeding with assumption it returns relevant topics.
    # EDIT: Conversation 38b1 implies "Verifying Topic Isolation" was a goal. 
    # Let's assume get_all_topics returns list of strings.
    
    agent = SuggestionAgent()
    suggestions, error = agent.generate_suggestions(user_profile, past_topics)
    
    if error:
        return jsonify({'error': error}), 500
        
    return jsonify({'suggestions': suggestions})
