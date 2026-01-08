from app.core.extensions import db
from app.core.models import Topic, StudyStep, Quiz, Flashcard
import logging
from sqlalchemy.exc import IntegrityError, OperationalError
from flask_login import current_user
from app.core.exceptions import (
    AuthenticationError,
    DatabaseOperationError,
    DatabaseConnectionError,
    DatabaseIntegrityError,
    ModelValidationError
)


def save_topic(topic_name, data):
    """
    Save topic data to PostgreSQL database.
    """
    logger = logging.getLogger(__name__)

    try:
        # Check authentication
        if not current_user.is_authenticated:
            raise AuthenticationError(
                "Attempt to save topic without authentication",
                error_code="AUTH100",
                debug_info={"topic_name": topic_name}
            )

        # Create/update topic
        topic = Topic.query.filter_by(
            name=topic_name,
            user_id=current_user.username).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.username)
            db.session.add(topic)

        # Update fields
        # Note: We rely on the JSON structure provided by the app
        # Fix: App uses 'plan', Model uses 'study_plan'
        topic.study_plan = data.get('plan', [])
        # topic.last_quiz_result = data.get('last_quiz_result') # MOVED to Quiz
        # table

        # Clear existing children to rebuild (simple strategy for full replace)
        # For efficiency, could compare, but this ensures consistency with "overwrite" behavior of JSON
        # However, deleting and re-creating might change IDs.
        # Let's try to update in place if possible, or just delete all children for now.
        # Given the app likely dumps the whole state, deleting children is
        # safer for consistency.

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
                # Ensure this is in JSON or default to index
                step_index=step_data.get('step_index', i),
                title=step_title,
                # Fix: App uses 'teaching_material', Model uses 'content'
                content=step_data.get(
                    'teaching_material') or step_data.get('content'),
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
                    # Storing the result here
                    result=data.get('last_quiz_result')
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

    except AuthenticationError:
        db.session.rollback()
        raise  # Re-raise custom exceptions
    except (ModelValidationError, DatabaseIntegrityError):
        db.session.rollback()
        raise  # Re-raise validation errors
    except IntegrityError as e:
        db.session.rollback()
        logger.error(
            f"Database integrity error saving topic {topic_name}: {e}")
        raise DatabaseIntegrityError(
            f"Topic '{topic_name}' may already exist or violates database constraints",
            error_code="DB100",
            debug_info={
                "topic_name": topic_name,
                "original_error": str(e)})
    except OperationalError as e:
        db.session.rollback()
        logger.error(f"Database connection error saving topic: {e}")
        raise DatabaseConnectionError(
            "Unable to connect to database",
            error_code="DB101",
            debug_info={"operation": "save_topic", "original_error": str(e)}
        )
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Unexpected error saving topic {topic_name}: {e}",
            exc_info=True)
        raise DatabaseOperationError(
            f"Failed to save topic: {str(e)}",
            operation="save_topic",
            error_code="DB102",
            debug_info={"topic_name": topic_name}
        )


def save_chat_history(topic_name, history):
    """
    Save chat history for a topic.
    """
    logger = logging.getLogger(__name__)

    try:
        if not current_user.is_authenticated:
            raise AuthenticationError(
                "Attempt to save chat history without authentication",
                error_code="AUTH101",
                debug_info={"topic_name": topic_name}
            )

        topic = Topic.query.filter_by(
            name=topic_name,
            user_id=current_user.username).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.username)
            db.session.add(topic)
            db.session.flush()  # Ensure ID exists

        from app.core.models import ChatSession

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

    except AuthenticationError:
        db.session.rollback()
        raise
    except OperationalError as e:
        db.session.rollback()
        logger.error(f"Database connection error saving chat history: {e}")
        raise DatabaseConnectionError(
            "Unable to connect to database",
            error_code="DB103",
            debug_info={
                "operation": "save_chat_history",
                "original_error": str(e)})
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Error saving chat history for {topic_name}: {e}",
            exc_info=True)
        raise DatabaseOperationError(
            f"Failed to save chat history: {str(e)}",
            operation="save_chat_history",
            error_code="DB104",
            debug_info={"topic_name": topic_name}
        )


def load_topic(topic_name):
    """
    Load topic data from PostgreSQL and reconstruct dictionary structure.
    Returns None if topic doesn't exist or user not authenticated (normal behavior for new topics).
    """
    logger = logging.getLogger(__name__)

    try:
        if not current_user.is_authenticated:
            return None  # Return None for unauthenticated - original behavior

        topic = Topic.query.filter_by(
            name=topic_name,
            user_id=current_user.username).first()
        if not topic:
            return None  # Topic doesn't exist yet - normal case for new topics

        data = {
            "name": topic.name,
            "plan": topic.study_plan or [],  # Map model 'study_plan' back to app 'plan'
            "last_quiz_result": None,  # Will populate from Quiz
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
        # If we have a plan, we want to return a list of steps matching that
        # plan
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
                "date": latest_quiz.created_at.isoformat() if latest_quiz.created_at else None}
            # Populate last_quiz_result from the quiz
            data["last_quiz_result"] = latest_quiz.result

        # Flashcards
        for card in topic.flashcards:
            data["flashcards"].append({
                "term": card.term,
                "definition": card.definition
            })

        return data

    except OperationalError as e:
        logger.error(f"Database connection error loading topic: {e}")
        raise DatabaseConnectionError(
            "Unable to connect to database",
            error_code="DB105",
            debug_info={"operation": "load_topic", "original_error": str(e)}
        )
    except Exception as e:
        logger.error(f"Error loading topic {topic_name}: {e}", exc_info=True)
        raise DatabaseOperationError(
            f"Failed to load topic: {str(e)}",
            operation="load_topic",
            error_code="DB106",
            debug_info={"topic_name": topic_name}
        )


def get_all_topics():
    """Get all topics for the current authenticated user."""
    logger = logging.getLogger(__name__)

    try:
        if not current_user.is_authenticated:
            return []  # Return empty list for unauthenticated - original behavior

        topics = Topic.query.with_entities(
            Topic.name).filter_by(
            user_id=current_user.username).all()
        return [t.name for t in topics]

    except OperationalError as e:
        logger.error(f"Database connection error getting topics: {e}")
        raise DatabaseConnectionError(
            "Unable to connect to database",
            error_code="DB107",
            debug_info={
                "operation": "get_all_topics",
                "original_error": str(e)})
    except Exception as e:
        logger.error(f"Error getting topics: {e}", exc_info=True)
        raise DatabaseOperationError(
            "Failed to retrieve topics",
            operation="get_all_topics",
            error_code="DB108"
        )


def delete_topic(topic_name):
    """Delete a topic and all its related  data."""
    logger = logging.getLogger(__name__)

    try:
        if not current_user.is_authenticated:
            return  # Silently return for unauthenticated - original behavior

        topic = Topic.query.filter_by(
            name=topic_name,
            user_id=current_user.username).first()
        if not topic:
            return  # Topic doesn't exist - silently return (original behavior)

        db.session.delete(topic)
        db.session.commit()
        logger.info(f"Successfully deleted topic: {topic_name}")

    except OperationalError as e:
        db.session.rollback()
        logger.error(f"Database connection error deleting topic: {e}")
        raise DatabaseConnectionError(
            "Unable to connect to database",
            error_code="DB109",
            debug_info={"operation": "delete_topic", "original_error": str(e)}
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting topic {topic_name}: {e}", exc_info=True)
        raise DatabaseOperationError(
            f"Failed to delete topic: {str(e)}",
            operation="delete_topic",
            error_code="DB110",
            debug_info={"topic_name": topic_name}
        )
