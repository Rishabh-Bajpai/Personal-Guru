from app.core.extensions import db
from app.core.models import Topic, ChapterMode, QuizMode, FlashcardMode, Feedback
import logging
import datetime
import os
import base64

from flask_login import current_user
from sqlalchemy.exc import IntegrityError, OperationalError
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

        topic = Topic.query.filter_by(name=topic_name, user_id=current_user.userid).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.userid)
            db.session.add(topic)
            db.session.flush()

        # Update topic fields
        topic.study_plan = data.get('plan', [])

        # Explicitly update modified_at when saving
        topic.modified_at = datetime.datetime.utcnow()

        # --- Handle Chapter Mode (Steps) ---
        incoming_msg_data = data.get('chapter_mode', [])
        # Support legacy 'steps' key if 'chapter_mode' is missing
        if not incoming_msg_data:
            incoming_msg_data = data.get('steps') or []

        # Maps for ID-based and Index-based lookup
        existing_steps_by_id = {s.id: s for s in topic.chapter_mode}
        existing_steps_by_index = {s.step_index: s for s in topic.chapter_mode}

        # Track processed IDs to know what to delete/keep
        # Note: ChapterMode relation is 'cascade="all, delete-orphan"', so we need to be careful.
        # But here we are iterating incoming data.

        processed_step_ids = set()

        for step_data in incoming_msg_data:
            step_index = step_data.get('step_index')
            step_id = step_data.get('id')

            # 1. Match by ID
            step = None
            if step_id and step_id in existing_steps_by_id:
                step = existing_steps_by_id[step_id]

            # 2. Fallback: Match by Index (e.g. initial creation or simple list update)
            # Only if index is provided and no ID match
            if not step and step_index is not None and step_index in existing_steps_by_index:
                 step = existing_steps_by_index[step_index]

            if step:
                # Update existing
                step.title = step_data.get('title', step.title)
                step.content = step_data.get('content') or step_data.get('teaching_material') or step.content

                if 'questions' in step_data:
                    step.questions = step_data['questions']

                if 'user_answers' in step_data:
                    step.user_answers = step_data['user_answers']

                if 'score' in step_data:
                    step.score = step_data['score']

                step.popup_chat_history = step_data.get('popup_chat_history', step.popup_chat_history)

                # Only update time_spent if valid positive integer
                inc_time = step_data.get('time_spent')
                if isinstance(inc_time, int) and inc_time >= 0:
                    step.time_spent = inc_time

                # Ensure step_index is correct (in case of reorder)
                if step_index is not None:
                     step.step_index = step_index

                step.podcast_audio_path = step_data.get('podcast_audio_path', step.podcast_audio_path)

                processed_step_ids.add(step.id)
            else:
                # Create New
                # Ensure we have required index
                if step_index is None:
                     # Auto-assign next index? Or strict error?
                     # Let's assume index is required or max+1
                     current_max = max([s.step_index for s in topic.chapter_mode] + [-1])
                     step_index = current_max + 1

                step = ChapterMode(
                    user_id=current_user.userid,
                    topic_id=topic.id,
                    step_index=step_index,
                    title=step_data.get('title'),
                    content=step_data.get('content') or step_data.get('teaching_material'),
                    questions=step_data.get('questions'),
                    user_answers=step_data.get('user_answers'),
                    score=step_data.get('score'),
                    popup_chat_history=step_data.get('popup_chat_history'),
                    time_spent=step_data.get('time_spent', 0),
                    podcast_audio_path=step_data.get('podcast_audio_path')
                )
                db.session.add(step)

            # --- Handle Feedback (Moved to dedicated table) ---
            # content_reference for this step: topic_{id}_step_{index}
            # Note: Topic ID might not be available if topic is new and flush not called?
            # We need to ensure topic is flushed.
            db.session.flush()
            content_ref = f"topic_{topic.id}_step_{step.step_index}"

            # Delete existing feedback for this step/user to overwrite with current state
            Feedback.query.filter_by(
                user_id=current_user.userid,
                content_reference=content_ref
            ).delete()



        # Delete removed steps
        for s in topic.chapter_mode:
            if s.id not in processed_step_ids and s not in db.session.new:
                db.session.delete(s)

        # --- Handle QuizMode ---
        # "quiz" key in JSON (legacy), "quiz_mode" is new standard
        q_data = data.get('quiz_mode') or data.get('quiz')
        if q_data:
             if True: # preserving indentation block
                 # Check existing quizzes
                 existing_quiz = topic.quiz_mode if topic.quiz_mode else None

                 if existing_quiz:
                     existing_quiz.questions = q_data.get('questions')
                     existing_quiz.score = q_data.get('score')
                     existing_quiz.result = data.get('last_quiz_result')
                     existing_quiz.time_spent = q_data.get('time_spent', 0)
                 else:
                     quiz = QuizMode(
                         user_id=current_user.userid,
                         topic_id=topic.id,
                         questions=q_data.get('questions'),
                         score=q_data.get('score'),
                         result=data.get('last_quiz_result'),
                         time_spent=q_data.get('time_spent', 0)
                     )
                     db.session.add(quiz)

        # --- Handle Flashcards ---
        incoming_cards = data.get('flashcard_mode') or data.get('flashcards') or []

        # Maps for ID-based and Term-based lookup
        existing_cards_by_id = {c.id: c for c in topic.flashcard_mode}
        existing_cards_by_term = {c.term: c for c in topic.flashcard_mode}

        # Track which existing cards are kept/updated
        processed_ids = set()

        for card_data in incoming_cards:
            term = card_data.get('term')
            if not term:
                continue

            card_id = card_data.get('id')
            matched_card = None

            # 1. Try match by ID
            if card_id and card_id in existing_cards_by_id:
                matched_card = existing_cards_by_id[card_id]

            # 2. Fallback: match by Term if ID mismatch or missing (e.g. generated but not saved yet)
            if not matched_card and term in existing_cards_by_term:
                matched_card = existing_cards_by_term[term]

            if matched_card:
                # Update existing
                matched_card.definition = card_data.get('definition', matched_card.definition)
                # Ensure we don't accidentally reset time_spent if not provided in update (though it should be)
                # But if provided as 0, we might want to allow it? Usually time accumulates.
                # Assuming incoming data is the "current state".
                val_time = card_data.get('time_spent')
                if val_time is not None:
                    matched_card.time_spent = val_time

                processed_ids.add(matched_card.id)
            else:
                # Create new
                new_card = FlashcardMode(
                    user_id=current_user.userid,
                    topic_id=topic.id,
                    term=term,
                    definition=card_data.get('definition'),
                    time_spent=card_data.get('time_spent', 0)
                )
                db.session.add(new_card)
                # Note: valid new_card.id won't exist until flush, but it's fine for this loop

        # Delete removed flashcards
        # If it wasn't processed (updated), it means it's not in the new list, so delete it.
        for c in topic.flashcard_mode:
            if c.id not in processed_ids and c not in db.session.new:
                db.session.delete(c)

        # --- Handle ChatMode ---
        # Ensure we save history and popup_history if they are in the data
        if 'chat_history' in data or 'popup_chat_history' in data:
            from app.core.models import ChatMode
            if not topic.chat_mode:
                chat_session = ChatMode(user_id=current_user.userid, topic_id=topic.id)
                db.session.add(chat_session)
            else:
                chat_session = topic.chat_mode

            from sqlalchemy.orm.attributes import flag_modified
            if 'chat_history' in data:
                chat_session.history = data['chat_history']
                flag_modified(chat_session, 'history')
            if 'chat_history_summary' in data:
                chat_session.history_summary = data['chat_history_summary']
                flag_modified(chat_session, 'history_summary')
            if 'popup_chat_history' in data:
                chat_session.popup_chat_history = data['popup_chat_history']
                flag_modified(chat_session, 'popup_chat_history')
            if 'chat_time_spent' in data:
                chat_session.time_spent = data['chat_time_spent']

            db.session.add(chat_session)

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

def save_chat_history(topic_name, history, history_summary=None, time_spent=0, popup_history=None):
    """
    Save chat history and optional summary for a topic.
    """
    logger = logging.getLogger(__name__)

    try:
        if not current_user.is_authenticated:
            raise AuthenticationError(
                "Attempt to save chat history without authentication",
                error_code="AUTH101",
                debug_info={"topic_name": topic_name}
            )

        topic = Topic.query.filter_by(name=topic_name, user_id=current_user.userid).first()
        if not topic:
            topic = Topic(name=topic_name, user_id=current_user.userid)
            db.session.add(topic)
            db.session.flush()  # Ensure ID exists

        from app.core.models import ChatMode

        if not topic.chat_mode:
            chat_session = ChatMode(user_id=current_user.userid, topic_id=topic.id, history=[])
            db.session.add(chat_session)
        else:
            chat_session = topic.chat_mode

        if time_spent > 0:
            chat_session.time_spent = (chat_session.time_spent or 0) + time_spent

        # Update history
        from sqlalchemy.orm.attributes import flag_modified
        chat_session.history = list(history)
        flag_modified(chat_session, 'history')

        if history_summary is not None:
             chat_session.history_summary = list(history_summary)
             flag_modified(chat_session, 'history_summary')

        if popup_history is not None:
             chat_session.popup_chat_history = list(popup_history)
             flag_modified(chat_session, 'popup_chat_history')

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
    logging.getLogger(__name__)

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
        "chat_history": (topic.chat_mode.history or []) if topic.chat_mode else [],
        "chat_history_summary": (topic.chat_mode.history_summary or []) if topic.chat_mode else [],
        "popup_chat_history": (topic.chat_mode.popup_chat_history or []) if topic.chat_mode else [],
        "chapter_mode": [],
        "quiz_mode": None,
        "flashcard_mode": []
    }


    # Initialize steps list matching the plan length
    plan = topic.study_plan or []
    # Create a map of existing steps by index
    existing_steps = {s.step_index: s for s in topic.chapter_mode}

    steps_data = []
    # If we have a plan, we want to return a list of steps matching that plan
    for i in range(len(plan)):
        step_model = existing_steps.get(i)
        if step_model:
            steps_data.append({
                "step_index": step_model.step_index,
                "id": step_model.id,
                "title": step_model.title,
                "content": step_model.content,
                "questions": step_model.questions,
                "user_answers": step_model.user_answers,
                "score": step_model.score,
                "popup_chat_history": step_model.popup_chat_history or [],
                "time_spent": step_model.time_spent or 0,
                # Include derived fields if needed, e.g. teaching_material is actually 'content' in model?
                # In model: content = db.Column(db.Text) # Markdown content
                # In app: key is 'teaching_material'
                "teaching_material": step_model.content,
                "podcast_audio_path": step_model.podcast_audio_path,
                "podcast_audio_content": None
            })

            # Load audio content if path exists
            if step_model.podcast_audio_path:
                audio_path = step_model.podcast_audio_path
                logging.info(f"DEBUG: Processing audio for step {step_model.step_index}. Raw path: {audio_path}")

                # If path doesn't exist as is, check if it's relative to app/static
                if not os.path.exists(audio_path):
                     # Try resolving relative to app/static
                     # Assuming project root is cwd. app/static is standard.
                     # We can also rely on flask static folder if available context, but here we are in storage.
                     candidate_path = os.path.join(os.getcwd(), 'app', 'static', os.path.basename(audio_path))
                     logging.info(f"DEBUG: Path not found. Trying candidate: {candidate_path}")
                     if os.path.exists(candidate_path):
                         audio_path = candidate_path
                         logging.info("DEBUG: Candidate found!")
                     else:
                         logging.debug("DEBUG: Candidate also not found.")

                if os.path.exists(audio_path):
                    try:
                        with open(audio_path, 'rb') as audio_file:
                            encoded_string = base64.b64encode(audio_file.read()).decode('utf-8')
                            steps_data[-1]["podcast_audio_content"] = encoded_string
                            logging.info(f"DEBUG: Successfully loaded and encoded audio for step {step_model.step_index}")
                    except Exception as e:
                         logging.warning(f"Failed to load audio file for topic {topic_name} step {step_model.step_index}: {e}")
                else:
                    logging.warning(f"Audio file not found at path: {step_model.podcast_audio_path} or resolved path {audio_path}")

            # Populate feedback from Feedback table
            content_ref = f"topic_{topic.id}_step_{step_model.step_index}"
            feedbacks = Feedback.query.filter_by(
                user_id=current_user.userid,
                content_reference=content_ref
            ).all()

            # Format back to list of strings or dicts as expected by frontend
            # Assuming simple strings for now or dicts if rating present
            steps_data[-1]['feedback'] = [f.comment for f in feedbacks]
        else:
            # Placeholder for steps not yet started/saved
            steps_data.append({})

    data["plan"] = plan
    data["chapter_mode"] = steps_data

    # QuizMode
    # Assuming one quiz per topic for now, similar to previous JSON usually
    if topic.quiz_mode:
        # Quiz is 1-to-1
        latest_quiz = topic.quiz_mode
        data["quiz_mode"] = {
            "questions": latest_quiz.questions,
            "score": latest_quiz.score,
            "date": latest_quiz.created_at.isoformat() if latest_quiz.created_at else None,
            "time_spent": latest_quiz.time_spent or 0
        }
        # Populate last_quiz_result from the quiz
        data["last_quiz_result"] = latest_quiz.result

    # Flashcards
    for card in topic.flashcard_mode:
        data["flashcard_mode"].append({
            "term": card.term,
            "definition": card.definition,
            "time_spent": card.time_spent or 0,
            "id": card.id
        })

    # Chat Mode time
    if topic.chat_mode:
        data["chat_time_spent"] = topic.chat_mode.time_spent or 0

    return data

def get_all_topics():
    """Get all topics for the current authenticated user."""
    logger = logging.getLogger(__name__)

    try:
        if not current_user.is_authenticated:
            return []  # Return empty list for unauthenticated - original behavior

        topics = Topic.query.with_entities(
            Topic.name).filter_by(
            user_id=current_user.userid).all()
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
            user_id=current_user.userid).first()
        if not topic:
            return  # Topic doesn't exist - silently return (original behavior)

        # Delete related chat sessions, chapter modes, quiz modes, flashcard modes, and plan revisions
        # before deleting the topic itself to avoid foreign key constraints.
        if topic.chat_mode:
            db.session.delete(topic.chat_mode)

        # Delete items in collections
        for item in topic.chapter_mode:
            db.session.delete(item)
        for item in topic.flashcard_mode:
            db.session.delete(item)
        for item in topic.plan_revisions:
            db.session.delete(item)

        # QuizMode is a one-to-one relationship (uselist=False), so no loop needed
        if topic.quiz_mode:
            db.session.delete(topic.quiz_mode)

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
