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

@main_bp.route('/background', methods=['GET', 'POST'])
def set_background():
    if request.method == 'POST':
        session['user_background'] = request.form['user_background']
        set_key(find_dotenv(), "USER_BACKGROUND", session['user_background'])
        return redirect(url_for('main.index'))

    current_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
    return render_template('background.html', user_background=current_background)

@main_bp.route('/delete/<topic_name>')
def delete_topic_route(topic_name):
    from app.core.storage import delete_topic
    delete_topic(topic_name)
    return redirect(url_for('main.index'))
