from app.core.extensions import db
from app.core.models import Topic, ChapterMode, QuizMode, FlashcardMode
import logging
import datetime

from flask_login import current_user

def save_topic(topic_name, data):
    """
    Save topic data to PostgreSQL database.
    """
    try:
        # Check if topic exists for current user
        # Handle case where current_user might not be authenticated (e.g. CLI usage?)
        # For now, assume web context.
        if not current_user.is_authenticated:
             logging.warning(f"Attempt to save topic {topic_name} without auth user.")
             raise Exception("User must be logged in to save topic.")

        topic = Topic.query.filter_by(name=topic_name, user_id=current_user.userid).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.userid)
            db.session.add(topic)
        
        # Update topic fields
        topic.study_plan = data.get('plan', []) 
        
        # Explicitly update modified_at when saving
        topic.modified_at = datetime.datetime.utcnow()
        
        # --- Handle ChapterMode (Steps) ---
        plan = data.get('plan', [])
        incoming_steps = data.get('steps', [])
        
        # Existing steps map: index -> instance
        existing_steps_map = {s.step_index: s for s in topic.steps}
        seen_indices = set()
        
        for i, step_data in enumerate(incoming_steps):
            step_index = step_data.get('step_index', i)
            seen_indices.add(step_index)
            
            step_title = step_data.get('title')
            if not step_title and plan and i < len(plan):
                step_title = plan[i]
                
            content = step_data.get('teaching_material') or step_data.get('content')
            
            if step_index in existing_steps_map:
                # Update existing
                step = existing_steps_map[step_index]
                step.title = step_title
                step.content = content
                step.questions = step_data.get('questions')
                step.user_answers = step_data.get('user_answers')
                step.feedback = step_data.get('feedback')
                step.score = step_data.get('score')
                step.chat_history = step_data.get('chat_history')
                step.time_spent = step_data.get('time_spent', 0)
            else:
                # Create new
                step = ChapterMode(
                    topics=topic,
                    step_index=step_index,
                    title=step_title,
                    content=content,
                    questions=step_data.get('questions'),
                    user_answers=step_data.get('user_answers'),
                    feedback=step_data.get('feedback'),
                    score=step_data.get('score'),
                    chat_history=step_data.get('chat_history'),
                    time_spent=step_data.get('time_spent', 0)
                )
                db.session.add(step)
        
        # Delete removed steps
        for idx, step in existing_steps_map.items():
            if idx not in seen_indices:
                db.session.delete(step)
            
        # --- Handle QuizMode ---
        # "quiz" key in JSON
        if 'quiz' in data:
             q_data = data.get('quiz')
             if q_data:
                 # Check existing quizzes
                 existing_quiz = topic.quizzes if topic.quizzes else None
                 
                 if existing_quiz:
                     existing_quiz.questions = q_data.get('questions')
                     existing_quiz.score = q_data.get('score')
                     existing_quiz.result = data.get('last_quiz_result')
                     existing_quiz.time_spent = q_data.get('time_spent', 0)
                 else:
                     quiz = QuizMode(
                         topics=topic,
                         questions=q_data.get('questions'),
                         score=q_data.get('score'),
                         result=data.get('last_quiz_result'), 
                         time_spent=q_data.get('time_spent', 0)
                     )
                     db.session.add(quiz)

        # --- Handle Flashcards ---
        # Flashcards are tricky without IDs. We'll match by TERM.
        incoming_cards = data.get('flashcards', [])
        existing_cards_map = {c.term: c for c in topic.flashcards}
        seen_terms = set()
        
        for card_data in incoming_cards:
            term = card_data.get('term')
            if not term: 
                continue
            seen_terms.add(term)
            
            if term in existing_cards_map:
                # Update
                card = existing_cards_map[term]
                card.definition = card_data.get('definition')
                card.time_spent = card_data.get('time_spent', 0)
            else:
                # Create
                card = FlashcardMode(
                    topics=topic,
                    term=term,
                    definition=card_data.get('definition'),
                    time_spent=card_data.get('time_spent', 0)
                )
                db.session.add(card)
        
        # Delete removed flashcards
        for term, card in existing_cards_map.items():
            if term not in seen_terms:
                db.session.delete(card)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving topic {topic_name}: {e}")
        raise e

def save_chat_history(topic_name, history, time_spent=0):
    """
    Save chat history for a topic.
    """
    try:
        if not current_user.is_authenticated:
             logging.warning(f"Attempt to save chat history {topic_name} without auth.")
             raise Exception("User must be logged in.")

        topic = Topic.query.filter_by(name=topic_name, user_id=current_user.userid).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.userid)
            db.session.add(topic)
            db.session.flush() # Ensure ID exists

        from app.core.models import ChatMode

        if not topic.chat_mode:
            chat_session = ChatMode(topics=topic, history=[])
            db.session.add(chat_session)
        else:
            chat_session = topic.chat_mode

        if time_spent > 0:
            chat_session.time_spent = (chat_session.time_spent or 0) + time_spent

        # Update history
        from sqlalchemy.orm.attributes import flag_modified
        chat_session.history = list(history)
        flag_modified(chat_session, 'history')
        db.session.add(chat_session)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving chat history for {topic_name}: {e}")
        raise e

def load_topic(topic_name):
    """
    Load topic data from PostgreSQL and reconstruct dictionary structure.
    """
    if not current_user.is_authenticated:
        return None

    topic = Topic.query.filter_by(name=topic_name, user_id=current_user.userid).first()
    if not topic:
        return None
        
    # User requested Modified At to update when opened ("any time")
    try:
        topic.modified_at = datetime.datetime.utcnow()
        db.session.commit()
    except Exception as e:
        logging.warning(f"Failed to update modify time on read for {topic_name}: {e}")
        # Don't block loading
        
    data = {
        "name": topic.name,
        "plan": topic.study_plan or [], # Map model 'study_plan' back to app 'plan'
        "last_quiz_result": None, # Will populate from Quiz
        "chat_history": topic.chat_mode.history if topic.chat_mode else [],
        "steps": [],
        "quiz": None,
        "flashcards": []
    }
    
    
    # Initialize steps list matching the plan length
    plan = topic.study_plan or []
    # Create a map of existing steps by index
    existing_steps = {s.step_index: s for s in topic.steps}
    
    steps_data = []
    # If we have a plan, we want to return a list of steps matching that plan
    for i in range(len(plan)):
        step_model = existing_steps.get(i)
        if step_model:
            steps_data.append({
                "step_index": step_model.step_index,
                "title": step_model.title,
                "content": step_model.content,
                "questions": step_model.questions,
                "user_answers": step_model.user_answers,
                "feedback": step_model.feedback,
                "score": step_model.score,
                "chat_history": step_model.chat_history or [],
                "time_spent": step_model.time_spent or 0,
                # Include derived fields if needed, e.g. teaching_material is actually 'content' in model?
                # In model: content = db.Column(db.Text) # Markdown content
                # In app: key is 'teaching_material'
                "teaching_material": step_model.content 
            })
        else:
            # Placeholder for steps not yet started/saved
            steps_data.append({})
            
    data["plan"] = plan
    data["steps"] = steps_data
        
    # QuizMode
    # Assuming one quiz per topic for now, similar to previous JSON usually
    if topic.quizzes:
        # Quiz is 1-to-1
        latest_quiz = topic.quizzes 
        data["quiz"] = {
            "questions": latest_quiz.questions,
            "score": latest_quiz.score,
            "date": latest_quiz.created_at.isoformat() if latest_quiz.created_at else None,
            "time_spent": latest_quiz.time_spent or 0
        }
        # Populate last_quiz_result from the quiz
        data["last_quiz_result"] = latest_quiz.result
        
    # Flashcards
    for card in topic.flashcards:
        data["flashcards"].append({
            "term": card.term,
            "definition": card.definition,
            "time_spent": card.time_spent or 0
        })
        
    # Chat Mode time
    if topic.chat_mode:
        data["chat_time_spent"] = topic.chat_mode.time_spent or 0

    return data

def get_all_topics():
    if not current_user.is_authenticated:
        return []

    topics = Topic.query.with_entities(Topic.name).filter_by(user_id=current_user.userid).all()
    return [t.name for t in topics]

def delete_topic(topic_name):
    if not current_user.is_authenticated:
        return 

    topic = Topic.query.filter_by(name=topic_name, user_id=current_user.userid).first()
    if topic:
        db.session.delete(topic)
        db.session.commit()

