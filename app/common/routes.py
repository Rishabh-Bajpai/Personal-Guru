from flask import Blueprint, render_template, request, session, redirect, url_for
from app.core.storage import get_all_topics, load_topic, save_topic

import os
from dotenv import set_key, find_dotenv

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

@main_bp.route('/user_profile', methods=['GET', 'POST'])
def user_profile():
    from app.common.models import User
    from app.common.extensions import db
    
    user = User.query.first()
    if not user:
        user = User()
        db.session.add(user)
        db.session.commit()
        
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
