from flask import Blueprint, render_template, request, session, redirect, url_for
from app.core.storage import get_all_topics, load_topic, save_topic
from app.core.agents import PlannerAgent
import os
from dotenv import set_key, find_dotenv

main_bp = Blueprint('main', __name__)
planner = PlannerAgent()

@main_bp.route('/', methods=['GET', 'POST'])
def index():
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

        # If user selected a non-chapter learning mode, show the appropriate selector or mode page.
        if mode and mode != 'chapter':
            if mode == 'quiz':
                return render_template('quiz/select.html', topic_name=topic_name) # Namespace adjusted
            
            topic_data = load_topic(topic_name) or {}
            flashcards = topic_data.get('flashcards', [])

            if mode == 'flashcard':
                 return render_template('flashcard/mode.html', topic_name=topic_name, flashcards=flashcards)
            
            if mode == 'reel':
                 return render_template('reel/mode.html', topic_name=topic_name)
                 
            if mode == 'chat':
                 return render_template('chat/mode.html', topic_name=topic_name)
                 
            try:
                # Fallback
                return render_template(f"{mode}/mode.html", topic_name=topic_name, flashcards=flashcards)
            except Exception:
                return render_template('index.html', topics=get_all_topics(), error=f"Mode {mode} not available")

        # Chapter Mode
        if mode == 'chapter':
            if load_topic(topic_name):
                return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=0))

            user_background = session.get('user_background', os.getenv("USER_BACKGROUND", "a beginner"))
            plan_steps, error = planner.generate_study_plan(topic_name, user_background)
            if error:
                return f"<h1>Error Generating Plan</h1><p>{plan_steps}</p>"

            topic_data = {
                "name": topic_name,
                "plan": plan_steps,
                "steps": [{} for _ in plan_steps]
            }
            save_topic(topic_name, topic_data)
            return redirect(url_for('chapter.learn_topic', topic_name=topic_name, step_index=0))

    topics = get_all_topics()
    topics_data = []
    for topic in topics:
        data = load_topic(topic)
        if data:
            plan = data.get('plan')
            flashcards = data.get('flashcards')
            quiz = data.get('quiz')
            has_plan = plan is not None and len(plan) > 0
            has_flashcards = flashcards is not None and len(flashcards) > 0
            has_quiz = quiz is not None and bool(quiz)
            topics_data.append({
                'name': topic,
                'has_plan': has_plan,
                'has_flashcards': has_flashcards,
                'has_quiz': has_quiz
            })
        else:
            topics_data.append({'name': topic, 'has_plan': False, 'has_flashcards': False, 'has_quiz': False})
    
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
