"""
Robust book content generation with persistent progress tracking.
"""

import datetime
import logging
from threading import Thread
from flask import current_app
from app.core.extensions import db
from app.core.models import Book, BookGenerationProgress, ChapterMode
from app.modes.chapter.agent import ChapterTeachingAgent
from app.modes.library.prompts import (
    get_librarian_search_prompt,
    get_librarian_generate_prompt,
)
from app.common.agents import PlannerAgent
from app.common.utils import call_llm
from app.core.exceptions import LLMResponseError

logger = logging.getLogger(__name__)


def start_book_generation(book_id, user_id, user_background):
    """
    Starts background generation for a book.
    Creates or updates progress tracking record.
    """
    # Create or get progress record
    progress = BookGenerationProgress.query.filter_by(book_id=book_id).first()

    book = Book.query.get(book_id)
    if not book:
        logger.error(f"Book {book_id} not found")
        return False

    total_topics = len(book.book_topics)

    if not progress:
        # Create new progress record
        progress = BookGenerationProgress(
            book_id=book_id,
            user_id=user_id,
            status="pending",
            total_topics=total_topics,
            current_topic_index=0,
            total_chapters=0,  # Will be calculated during generation
            completed_chapters=0,
            current_message="Initializing generation...",
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.session.add(progress)
        db.session.commit()
    else:
        # Update existing progress record
        if progress.status == "generating":
            logger.info(f"Book {book_id} is already generating")
            return True

        # Reset progress for retry
        progress.status = "pending"
        progress.total_topics = total_topics
        progress.current_topic_index = 0
        progress.error_message = None
        progress.current_message = "Restarting generation..."
        progress.started_at = datetime.datetime.now(datetime.timezone.utc)
        progress.completed_at = None
        db.session.commit()

    # Start background thread
    app_context = current_app._get_current_object().app_context()
    thread = Thread(
        target=generate_book_content_background,
        args=(app_context, book_id, user_id, user_background),
    )
    thread.daemon = True
    thread.start()

    return True


def generate_book_content_background(app_context, book_id, user_id, user_background):
    """
    Background task to generate all content for a book with persistent progress tracking.
    """
    with app_context:
        progress = None
        try:
            # Get progress record
            progress = BookGenerationProgress.query.filter_by(book_id=book_id).first()
            if not progress:
                logger.error(f"Progress record not found for book {book_id}")
                return

            # Update status to generating
            progress.status = "generating"
            progress.started_at = datetime.datetime.now(datetime.timezone.utc)
            db.session.commit()

            # Get book and topics
            book = Book.query.get(book_id)
            if not book:
                raise Exception(f"Book {book_id} not found")

            planner = PlannerAgent()
            teacher = ChapterTeachingAgent()

            total_topics = len(book.book_topics)
            progress.total_topics = total_topics

            # Calculate accurate chapter counts at start
            # This ensures we have the correct baseline even on resume
            total_chapters = 0
            completed_chapters = 0
            topics_without_plans = 0

            for bt in book.book_topics:
                topic = bt.topic
                chapters = ChapterMode.query.filter_by(topic_id=topic.id).all()
                if chapters:
                    total_chapters += len(chapters)
                    # Count completed chapters
                    for ch in chapters:
                        if ch.content:
                            completed_chapters += 1
                else:
                    # Estimate 5 chapters per topic without a plan
                    total_chapters += 5
                    topics_without_plans += 1

            progress.total_chapters = total_chapters
            progress.completed_chapters = completed_chapters
            db.session.commit()

            logger.info(
                f"Book {book_id}: Starting generation - {total_chapters} total chapters ({topics_without_plans} topics need plans), {completed_chapters} already complete"
            )

            # Generate content for each topic
            for idx, bt in enumerate(
                sorted(book.book_topics, key=lambda x: x.order_index)
            ):
                topic = bt.topic
                progress.current_topic_index = idx
                progress.current_message = (
                    f"Processing topic {idx + 1}/{total_topics}: {topic.name}"
                )
                db.session.commit()

                # Check if topic has chapters
                chapters = (
                    ChapterMode.query.filter_by(topic_id=topic.id)
                    .order_by(ChapterMode.step_index)
                    .all()
                )

                if not chapters:
                    # Generate study plan
                    progress.current_message = f"Generating plan for: {topic.name}"
                    db.session.commit()

                    try:
                        plan_steps = planner.generate_study_plan(
                            topic.name, user_background
                        )

                        # Save plan directly to database (bypass storage.py which needs current_user)
                        topic.study_plan = plan_steps

                        # Create chapter records
                        for i, step_title in enumerate(plan_steps):
                            chapter = ChapterMode(
                                user_id=user_id,
                                topic_id=topic.id,
                                step_index=i,
                                title=step_title,
                            )
                            db.session.add(chapter)

                        db.session.commit()

                        # Update total chapters count: replace estimate (5) with actual count
                        actual_chapters = len(plan_steps)
                        chapters_diff = actual_chapters - 5  # Difference from estimate
                        progress.total_chapters = (
                            progress.total_chapters + chapters_diff
                        )
                        db.session.commit()

                        logger.info(
                            f"Generated plan for {topic.name}: {actual_chapters} chapters (estimate was 5, diff: {chapters_diff}). New total: {progress.total_chapters}"
                        )

                        # Reload chapters
                        chapters = (
                            ChapterMode.query.filter_by(topic_id=topic.id)
                            .order_by(ChapterMode.step_index)
                            .all()
                        )
                    except Exception as e:
                        logger.error(f"Failed to generate plan for {topic.name}: {e}")
                        progress.current_message = (
                            f"Error generating plan for {topic.name}: {str(e)}"
                        )
                        db.session.commit()
                        continue

                # Generate content for each chapter
                for ch_idx, chapter in enumerate(chapters):
                    if chapter.content:
                        # Already has content, skip
                        logger.debug(
                            f"Skipping {topic.name} chapter {ch_idx + 1} - already has content"
                        )
                        continue

                    progress.current_message = (
                        f"Writing {topic.name}: Chapter {ch_idx + 1}/{len(chapters)}"
                    )
                    db.session.commit()

                    try:
                        # Get plan steps from topic
                        plan_steps = topic.study_plan if topic.study_plan else []
                        step_title = (
                            plan_steps[chapter.step_index]
                            if chapter.step_index < len(plan_steps)
                            else chapter.title or "Chapter Content"
                        )

                        logger.info(
                            f"Generating content for {topic.name} chapter {ch_idx + 1}: {step_title}"
                        )

                        # Generate teaching material
                        material = teacher.generate_teaching_material(
                            step_title, plan_steps, user_background, None
                        )

                        # Save to database directly
                        chapter.content = material
                        progress.completed_chapters += 1
                        db.session.commit()

                        logger.info(
                            f"Completed {topic.name} chapter {ch_idx + 1}. Progress: {progress.completed_chapters}/{progress.total_chapters}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to generate content for {topic.name} chapter {chapter.step_index}: {e}"
                        )
                        progress.current_message = (
                            f"Error in {topic.name} chapter {ch_idx + 1}: {str(e)}"
                        )
                        db.session.commit()
                        # Continue with next chapter even if one fails

            # Verify completion before marking as complete
            final_check_complete = True
            for bt in book.book_topics:
                chapters = ChapterMode.query.filter_by(topic_id=bt.topic.id).all()
                if not chapters:
                    final_check_complete = False
                    break
                for ch in chapters:
                    if not ch.content:
                        final_check_complete = False
                        break
                if not final_check_complete:
                    break

            if final_check_complete:
                # Attempt book cover generation before marking complete
                progress.current_message = "Generating book cover..."
                db.session.commit()

                try:
                    _generate_book_cover(book)
                except Exception as cover_err:
                    logger.warning(
                        f"Book cover generation failed for {book_id} (non-fatal): {cover_err}"
                    )

                # Mark as completed
                progress.status = "completed"
                progress.current_message = "Generation complete!"
                progress.completed_at = datetime.datetime.now(datetime.timezone.utc)
                db.session.commit()
                logger.info(f"Book {book_id} generation completed successfully")
            else:
                # Some chapters failed, mark as error
                progress.status = "error"
                progress.error_message = "Some chapters failed to generate"
                progress.completed_at = datetime.datetime.now(datetime.timezone.utc)
                db.session.commit()
                logger.warning(
                    f"Book {book_id} generation incomplete - some chapters failed"
                )

        except Exception as e:
            logger.error(f"Book generation failed for {book_id}: {e}", exc_info=True)
            if progress:
                progress.status = "error"
                progress.error_message = str(e)
                progress.completed_at = datetime.datetime.now(datetime.timezone.utc)
                db.session.commit()


def get_generation_progress(book_id):
    """
    Get the current generation progress for a book.
    Returns a dictionary with progress information.
    """
    progress = BookGenerationProgress.query.filter_by(book_id=book_id).first()

    # Check if book actually needs generation
    book = Book.query.get(book_id)
    if not book:
        return {"status": "error", "message": "Book not found"}

    # Check if book has incomplete content
    needs_generation = False
    total_chapters_actual = 0
    completed_chapters_actual = 0

    for bt in book.book_topics:
        chapters = ChapterMode.query.filter_by(topic_id=bt.topic.id).all()
        if not chapters:
            needs_generation = True
            break
        total_chapters_actual += len(chapters)
        for ch in chapters:
            if ch.content:
                completed_chapters_actual += 1
            else:
                needs_generation = True

    # If no progress record exists
    if not progress:
        if needs_generation:
            return {
                "status": "pending",
                "message": "Ready to generate",
                "book_id": book_id,
                "total_chapters": total_chapters_actual,
                "completed_chapters": completed_chapters_actual,
            }
        else:
            return {
                "status": "completed",
                "message": "Already generated",
                "book_id": book_id,
                "total_chapters": total_chapters_actual,
                "completed_chapters": completed_chapters_actual,
            }

    # Determine if progress needs to be reconciled or updated
    if progress.modified_at and progress.modified_at.tzinfo is None:
        now = datetime.datetime.utcnow()
    else:
        now = datetime.datetime.now(datetime.timezone.utc)
    needs_update = False

    # Sequential state transitions (if/elif ensures only one transition per check)
    if not needs_generation and progress.status != "completed":
        # Book is actually complete but progress says otherwise, fix it
        logger.info(
            f"Book {book_id} is complete but status was {progress.status}, fixing"
        )
        progress.status = "completed"
        progress.current_message = "Generation complete!"
        progress.completed_at = now
        needs_update = True

    elif progress.status == "completed" and needs_generation:
        # User added new topics to a previously completed book
        logger.info(f"Book {book_id} marked complete but needs more content, resetting")
        progress.status = "pending"
        progress.current_message = "Additional content needed"
        needs_update = True

    elif progress.status == "error" and needs_generation:
        # Retry logic for failed generations
        logger.info(f"Book {book_id} had error, resetting to pending for retry")
        progress.status = "pending"
        progress.error_message = None
        progress.current_message = "Ready to retry generation"
        needs_update = True

    elif progress.status == "generating" and progress.modified_at:
        # Check for stale background threads (stuck or crashed)
        time_since_update = (now - progress.modified_at).total_seconds()
        if time_since_update > 300:
            if needs_generation:
                logger.warning(
                    f"Book {book_id} generation appears stale ({time_since_update}s), resetting to pending"
                )
                progress.status = "pending"
                progress.current_message = "Generation interrupted, click to resume"
            else:
                # Thread stopped but work was actually done
                progress.status = "completed"
                progress.current_message = "Generation complete!"
                progress.completed_at = now
            needs_update = True

    # Always sync counts and commit once if state or progress changed
    if (
        needs_update
        or progress.total_chapters != total_chapters_actual
        or progress.completed_chapters != completed_chapters_actual
    ):
        progress.total_chapters = total_chapters_actual
        progress.completed_chapters = completed_chapters_actual
        db.session.commit()

    return progress.to_dict()


def get_all_active_generations(user_id):
    """
    Get all active book generations for a user.
    Returns a list of progress dictionaries.
    """
    active_progress = (
        BookGenerationProgress.query.filter_by(user_id=user_id)
        .filter(BookGenerationProgress.status.in_(["pending", "generating"]))
        .all()
    )

    return [p.to_dict() for p in active_progress]


def _generate_book_cover(book):
    """
    Attempt to generate a book cover image using ComfyUI.
    Saves to data/book_cover/cover_<book_id>.png and updates book.cover_path.
    """
    import os
    import werkzeug.utils
    from flask import current_app

    server_address = current_app.config.get("COMFYUI_SERVER_ADDRESS", "localhost:8188")
    workflow_path = current_app.config.get("COMFYUI_WORKFLOW_PATH")

    if not workflow_path or not os.path.exists(workflow_path):
        logger.warning(
            f"ComfyUI workflow not found at {workflow_path}, skipping cover generation"
        )
        return

    from app.modes.library.book_cover import BookCoverService

    service = BookCoverService(server_address, workflow_path)

    # Build output path relative to project root
    # We use a relative path for the DB to ensure portability between local and Docker
    rel_cover_dir = os.path.join("data", "book_cover")
    data_root = current_app.config.get("DATA_DIR") or current_app.root_path
    abs_cover_dir = os.path.join(data_root, rel_cover_dir)
    os.makedirs(abs_cover_dir, exist_ok=True)

    filename = werkzeug.utils.secure_filename(f"cover_{book.id}.png")
    abs_output_path = os.path.join(abs_cover_dir, filename)
    rel_output_path = os.path.join(rel_cover_dir, filename)

    # Refine prompt using LLM for better quality
    from app.modes.library.prompts import get_book_cover_prompt

    refined_prompt = None
    try:
        llm_prompt = get_book_cover_prompt(
            book.title, book.description or "A book about " + book.title
        )
        refined_prompt = call_llm(llm_prompt, is_json=False)
        logger.info(f"Refined cover prompt for book {book.id}: {refined_prompt}")
    except Exception as e:
        logger.warning(
            f"Failed to refine cover prompt with LLM: {e}. Falling back to basic prompt."
        )

    success, error_msg = service.generate_cover(
        book.title,
        book.description or "",
        abs_output_path,
        refined_prompt=refined_prompt,
    )

    if success:
        book.cover_path = rel_output_path
        db.session.commit()
        logger.info(f"Book cover saved for book {book.id}: {rel_output_path}")
    else:
        logger.warning(f"Book cover generation failed for book {book.id}: {error_msg}")


class LibrarianAgent:
    """
    Agent responsible for discovering, clustering, and generating books.
    """

    def search_and_suggest(self, query, vector_db, current_topics):
        """
        Searches existing topics using VectorDB and suggests a curated book.

        Args:
            query (str): The user's search query.
            vector_db (VectorDB): The instantiated and loaded VectorDB.
            current_topics (list): List of user's existing topics to match against.

        Returns:
            dict: Suggested book structure with title, description, and list of matched topic IDs.
        """
        # 1. Search VectorDB for relevant content
        search_results = vector_db.search(query, top_k=15)

        if not search_results:
            return None

        # 2. Prepare context for LLM
        context_items = []
        for res in search_results:
            topic_id = res["metadata"].get("topic_id")
            topic_title = res["metadata"].get("title", "Unknown")
            context_items.append(
                f"Topic ID {topic_id}: {topic_title} - {res['content'][:150]}"
            )

        context = "\n".join(context_items)

        prompt = get_librarian_search_prompt(query, context)

        try:
            response = call_llm(prompt, is_json=True)
            return response
        except LLMResponseError as e:
            logging.error(f"LibrarianAgent search failed: {e}")
            return None

    def generate_book(self, query, user_background):
        """
        Generates a completely new book structure for topics the user hasn't learned yet.

        Args:
            query (str): The subject the user wants to learn.
            user_background (str): The user's background.

        Returns:
            dict: Book structure with title, description, and list of new topic names.
        """
        prompt = get_librarian_generate_prompt(query, user_background)

        try:
            response = call_llm(prompt, is_json=True)
            return response
        except LLMResponseError as e:
            logging.error(f"LibrarianAgent generation failed: {e}")
            # Fallback
            return {
                "title": f"Learning {query}",
                "description": f"An auto-generated book about {query}",
                "topics": [
                    f"Introduction to {query}",
                    f"Core Concepts of {query}",
                    f"Advanced {query}",
                ],
            }
