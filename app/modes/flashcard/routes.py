from flask import render_template, request, session, redirect, url_for
from . import flashcard_bp
from app.core.storage import load_topic, save_topic
from .agent import FlashcardTeachingAgent
import os

teacher = FlashcardTeachingAgent()

@flashcard_bp.route('/<topic_name>')
def mode(topic_name):
    """Display flashcard mode with saved flashcards or generation UI."""
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404
    
    flashcards = topic_data.get('flashcards', [])
    return render_template('flashcard/mode.html', topic_name=topic_name, flashcards=flashcards)

@flashcard_bp.route('/generate', methods=['POST'])
def generate_flashcards_route():
    data = request.get_json() or {}
    topic_name = data.get('topic')
    count = data.get('count', 'auto')

    if not topic_name:
        return {"error": "No topic provided"}, 400

    user_background = os.getenv('USER_BACKGROUND', 'a beginner')

    # Determine flashcard count
    if isinstance(count, str) and count.lower() == 'auto':
        num, error = teacher.get_flashcard_count_for_topic(topic_name, user_background=user_background)
        if error:
            print(f"Error getting flashcard count: {error}")
            num = 25
    else:
        try:
            num = int(count)
        except (ValueError, TypeError):
            num = 25

    # Refetch background just in case
    user_background = os.getenv('USER_BACKGROUND', 'a beginner')

    cards, error = teacher.generate_teaching_material(topic_name, count=num, user_background=user_background)
    if error:
        return {"error": cards}, 500

    # Persist flashcards
    topic_data = load_topic(topic_name) or {"name": topic_name, "plan": [], "steps": []}
    topic_data['flashcards'] = cards
    save_topic(topic_name, topic_data)

    return {"flashcards": cards}
