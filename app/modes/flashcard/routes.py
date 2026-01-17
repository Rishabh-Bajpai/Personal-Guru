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
        flashcards = topic_data.get('flashcard_mode', [])

    return render_template(
        'flashcard/mode.html',
        topic_name=topic_name,
        flashcards=flashcards)


@flashcard_bp.route('/generate', methods=['POST'])
def generate_flashcards_route():
    """
    Generate flashcards for a topic.

    ---
    tags:
      - Flashcards
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            topic:
              type: string
            count:
              type: string
              description: Number of cards or 'auto'
              default: 'auto'
    responses:
      200:
        description: Generated flashcards
        schema:
          type: object
          properties:
            flashcards:
              type: array
              items:
                type: object
      400:
        description: No topic provided
    """
    data = request.get_json() or {}
    topic_name = data.get('topic')
    count = data.get('count', 'auto')

    if not topic_name:
        return {"error": "No topic provided"}, 400

    from app.common.utils import get_user_context
    user_background = get_user_context()

    # Determine flashcard count
    if isinstance(count, str) and count.lower() == 'auto':
        try:
            num = teacher.get_flashcard_count_for_topic(
                topic_name, user_background=user_background)
        except Exception as error:
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

    try:
        cards = teacher.generate_teaching_material(
            topic_name, count=num, user_background=user_background)
    except Exception as error:
        return {"error": str(error)}, 500

    # Persist flashcards
    topic_data = load_topic(topic_name) or {
        "name": topic_name, "plan": [], "steps": []}
    topic_data['flashcard_mode'] = cards
    save_topic(topic_name, topic_data)

    return {"flashcard_mode": cards, "flashcards": cards}

@flashcard_bp.route('/<topic_name>/update_time', methods=['POST'])
def update_time(topic_name):
    """Update time spent on flashcards."""
    try:
        time_spent = int(request.form.get('time_spent', 0))
    except (ValueError, TypeError):
        time_spent = 0

    if time_spent > 0:
        topic_data = load_topic(topic_name)
        if topic_data and topic_data.get('flashcard_mode'):
             if len(topic_data['flashcard_mode']) > 0:
                 topic_data['flashcard_mode'][0]['time_spent'] = (topic_data['flashcard_mode'][0].get('time_spent', 0) or 0) + time_spent
                 save_topic(topic_name, topic_data)

    return '', 204

@flashcard_bp.route('/<topic_name>/update_progress', methods=['POST'])
def update_progress(topic_name):
    """
    Update progress/time-spent for specific flashcards.

    ---
    tags:
      - Flashcards
    parameters:
      - name: topic_name
        in: path
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            flashcards:
              type: array
              items:
                type: object
    responses:
      200:
        description: Progress updated successfully
      404:
        description: Topic not found
    """
    data = request.json
    topic_data = load_topic(topic_name)
    if not topic_data:
        return {"error": "Topic not found"}, 404

    # Re-reading logic:
    # incoming data['flashcards'] is list of {term:..., time_spent:...}
    # Let's map incoming by ID and Term
    incoming_by_id = {}
    incoming_by_term = {}
    for item in data.get('flashcards', []):
        if 'id' in item:
            incoming_by_id[item['id']] = item.get('time_spent', 0)
        if 'term' in item:
            incoming_by_term[item['term']] = item.get('time_spent', 0)

    for card in topic_data.get('flashcard_mode', []):
        added_time = 0
        if card.get('id') in incoming_by_id:
            added_time = incoming_by_id[card['id']]
        elif card.get('term') in incoming_by_term:
            added_time = incoming_by_term[card['term']]

        if added_time > 0:
            card['time_spent'] = (card.get('time_spent', 0) or 0) + added_time

    save_topic(topic_name, topic_data)
    return {"status": "success"}

@flashcard_bp.route('/<topic_name>/export/pdf')
def export_pdf(topic_name):
    """Export flashcards as a PDF."""
    topic_data = load_topic(topic_name)
    if not topic_data:
        return "Topic not found", 404

    flashcards = topic_data.get('flashcard_mode', [])

    html = render_template(
        'flashcard/export.html',
        topic_name=topic_name,
        flashcards=flashcards)
    pdf = HTML(string=html).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={topic_name}_flashcards.pdf'
    return response
