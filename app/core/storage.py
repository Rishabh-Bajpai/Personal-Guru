from app.common.extensions import db
from app.common.models import Topic, StudyStep, Quiz, Flashcard
import logging

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

        topic = Topic.query.filter_by(name=topic_name, user_id=current_user.username).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.username)
            db.session.add(topic)
        
        # Update fields
        # Note: We rely on the JSON structure provided by the app
        # Fix: App uses 'plan', Model uses 'study_plan'
        topic.study_plan = data.get('plan', []) 
        # topic.last_quiz_result = data.get('last_quiz_result') # MOVED to Quiz table
        
        # Clear existing children to rebuild (simple strategy for full replace)
        # For efficiency, could compare, but this ensures consistency with "overwrite" behavior of JSON
        # However, deleting and re-creating might change IDs.
        # Let's try to update in place if possible, or just delete all children for now.
        # Given the app likely dumps the whole state, deleting children is safer for consistency.
        
        # Delete existing relationships
        StudyStep.query.filter_by(topic_id=topic.id).delete()
        Quiz.query.filter_by(topic_id=topic.id).delete()
        Flashcard.query.filter_by(topic_id=topic.id).delete()
        
        # Steps
        plan = data.get('plan', [])
        for i, step_data in enumerate(data.get('steps', [])):
            step_title = step_data.get('title')
            if not step_title and plan and i < len(plan):
                step_title = plan[i]

            step = StudyStep(
                topic=topic,
                step_index=step_data.get('step_index', i), # Ensure this is in JSON or default to index
                title=step_title,
                # Fix: App uses 'teaching_material', Model uses 'content'
                content=step_data.get('teaching_material') or step_data.get('content'),
                questions=step_data.get('questions'),
                user_answers=step_data.get('user_answers'),
                feedback=step_data.get('feedback'),
                score=step_data.get('score'),
                chat_history=step_data.get('chat_history')
            )
            db.session.add(step)
            
        # Quiz
        # "quiz" key in JSON
        if 'quiz' in data:
             q_data = data.get('quiz')
             if q_data:
                 quiz = Quiz(
                     topic=topic,
                     questions=q_data.get('questions'),
                     score=q_data.get('score'),
                     result=data.get('last_quiz_result') # Storing the result here
                 )
                 db.session.add(quiz)

        # Flashcards
        for card_data in data.get('flashcards', []):
            card = Flashcard(
                topic=topic,
                term=card_data.get('term'),
                definition=card_data.get('definition')
            )
            db.session.add(card)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving topic {topic_name}: {e}")
        raise e

def save_chat_history(topic_name, history):
    """
    Save chat history for a topic.
    """
    try:
        if not current_user.is_authenticated:
             logging.warning(f"Attempt to save chat history {topic_name} without auth.")
             raise Exception("User must be logged in.")

        topic = Topic.query.filter_by(name=topic_name, user_id=current_user.username).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.username)
            db.session.add(topic)
            db.session.flush() # Ensure ID exists

        from app.common.models import ChatSession

        if not topic.chat_session:
            chat_session = ChatSession(topic=topic, history=[])
            db.session.add(chat_session)
        else:
            chat_session = topic.chat_session

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

    topic = Topic.query.filter_by(name=topic_name, user_id=current_user.username).first()
    if not topic:
        return None
        
    data = {
        "name": topic.name,
        "plan": topic.study_plan or [], # Map model 'study_plan' back to app 'plan'
        "last_quiz_result": None, # Will populate from Quiz
        "chat_history": topic.chat_session.history if topic.chat_session else [],
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
        
    # Quiz
    # Assuming one quiz per topic for now, similar to previous JSON usually
    if topic.quizzes:
        # Check if models.py defined strict 1-to-many. It did.
        # But if the app treats it as a single object...
        # I'll take the latest one.
        latest_quiz = topic.quizzes[-1] 
        data["quiz"] = {
            "questions": latest_quiz.questions,
            "score": latest_quiz.score,
            "date": latest_quiz.created_at.isoformat() if latest_quiz.created_at else None
        }
        # Populate last_quiz_result from the quiz
        data["last_quiz_result"] = latest_quiz.result
        
    # Flashcards
    for card in topic.flashcards:
        data["flashcards"].append({
            "term": card.term,
            "definition": card.definition
        })
        
    return data

def get_all_topics():
    if not current_user.is_authenticated:
        return []

    topics = Topic.query.with_entities(Topic.name).filter_by(user_id=current_user.username).all()
    return [t.name for t in topics]

def delete_topic(topic_name):
    if not current_user.is_authenticated:
        return 

    topic = Topic.query.filter_by(name=topic_name, user_id=current_user.username).first()
    if topic:
        db.session.delete(topic)
        db.session.commit()

