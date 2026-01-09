from flask import render_template, request, make_response
from . import flashcard_bp
from app.common.storage import load_topic, save_topic
from .agent import FlashcardTeachingAgent
from weasyprint import HTML

teacher = FlashcardTeachingAgent()

@flashcard_bp.route('/<topic_name>')
def mode(topic_name):
    """Display flashcard mode with saved flashcards or generation UI."""
    topic_data = load_topic(topic_name)
    if not topic_data:
        # Topic doesn't exist yet, allow user to generate content
        flashcards = []
    else:
        flashcards = topic_data.get('flashcards', [])
    
    return render_template('flashcard/mode.html', topic_name=topic_name, flashcards=flashcards)

@flashcard_bp.route('/generate', methods=['POST'])
def generate_flashcards_route():
    data = request.get_json() or {}
    topic_name = data.get('topic')
    count = data.get('count', 'auto')

    if not topic_name:
        return {"error": "No topic provided"}, 400

    from app.common.utils import get_user_context
    user_background = get_user_context()

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
    from app.common.utils import get_user_context
    user_background = get_user_context()

    cards, error = teacher.generate_teaching_material(topic_name, count=num, user_background=user_background)
    if error:
        return {"error": cards}, 500

    # Persist flashcards
    topic_data = load_topic(topic_name) or {"name": topic_name, "plan": [], "steps": []}
    topic_data['flashcards'] = cards
    save_topic(topic_name, topic_data)

    return {"flashcards": cards}

@flashcard_bp.route('/<topic_name>/update_time', methods=['POST'])
def update_time(topic_name):
    try:
        time_spent = int(request.form.get('time_spent', 0))
    except (ValueError, TypeError):
        time_spent = 0
        
    if time_spent > 0:
        topic_data = load_topic(topic_name)
        if topic_data and topic_data.get('flashcards'):
             # Accumulate time generally for the topic or distribute?
             # FlashcardMode table has time_spent per card.
             # If we just track "page time", where does it go?
             # We can distribute it among all cards or just pick the first one?
             # OR, we should rely on update_progress for specific cards.
             # BUT the user asked for "time spent in that mode".
             # If they just stare at the screen, we should count it.
             # Let's add it to the first card as a fallback if no specific interaction?
             # Or maybe generic topic time? Topic doesn't have time_spent.
             # Let's just return 204 for now as the update_progress covers active use.
             # Actually, let's distribute it evenly or add to first card to not lose it.
             # Better: do nothing if we want to rely on detailed tracking, 
             # but `time_tracker.js` is generic.
             # Let's add it to the first flashcard to ensure it is captured.
             if len(topic_data['flashcards']) > 0:
                 topic_data['flashcards'][0]['time_spent'] = (topic_data['flashcards'][0].get('time_spent', 0) or 0) + time_spent
                 save_topic(topic_name, topic_data)
             
    return '', 204

@flashcard_bp.route('/<topic_name>/update_progress', methods=['POST'])
def update_progress(topic_name):
    data = request.json
    topic_data = load_topic(topic_name)
    if not topic_data:
        return {"error": "Topic not found"}, 404
        
    # Expecting data['flashcards'] to be a list of {term: ..., time_spent: ...}
    updates = {item['term']: item.get('time_spent', 0) for item in data.get('flashcards', [])}
    
    for card in topic_data.get('flashcards', []):
        if card['term'] in updates:
            # Accumulate time
            card['time_spent'] = (card.get('time_spent', 0) or 0) + updates[card['term']]
            
    save_topic(topic_name, topic_data)
    return {"status": "success"}

@flashcard_bp.route('/<topic_name>/export/pdf')
def export_pdf(topic_name):
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404
    
    flashcards = topic_data.get('flashcards', [])
    
    html = render_template('flashcard/export.html', topic_name=topic_name, flashcards=flashcards)
    pdf = HTML(string=html).write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={topic_name}_flashcards.pdf'
    return response
