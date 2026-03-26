"""Book content generation with in-memory progress tracking."""

import datetime
import logging
import os
from threading import Lock, Thread
from flask import current_app
from sqlalchemy import case, func
from app.core.extensions import db
from app.core.models import Book, ChapterMode
from app.modes.chapter.agent import ChapterTeachingAgent
from app.modes.library.prompts import (
    get_librarian_search_prompt,
    get_librarian_generate_prompt,
)
from app.common.agents import PlannerAgent
from app.common.utils import call_llm
from app.core.exceptions import LLMResponseError

logger = logging.getLogger(__name__)

_GENERATION_STALE_SECONDS = 300
_TERMINAL_STATE_TTL_SECONDS = 600
# NOTE: This state is process-local and only safe in single-process deployments.
_generation_progress = {}
_generation_lock = Lock()


def _utcnow():
    """Return the current timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


def _get_data_root():
    """Return the project data root used for generated assets."""
    return current_app.config.get("DATA_DIR") or os.path.abspath(
        os.path.join(current_app.root_path, "..")
    )


def _create_generation_state(book_id, user_id, total_topics):
    """Build the initial in-memory progress state for a book run."""
    now = _utcnow()
    return {
        "book_id": book_id,
        "user_id": user_id,
        "status": "pending",
        "phase": "structuring",
        "total_topics": total_topics,
        "current_topic_index": 0,
        "planned_total_chapters": 0,
        "message": "Initializing generation...",
        "error": None,
        "started_at": now,
        "completed_at": None,
        "last_update": now,
    }


def _set_generation_state(book_id, **updates):
    """Update an existing in-memory generation state and bump its timestamp."""
    with _generation_lock:
        state = _generation_progress.get(book_id)
        if state is None:
            return None
        state.update(updates)
        state["last_update"] = _utcnow()
        return dict(state)


def _get_generation_state(book_id):
    """Return a copy of the in-memory generation state for a book."""
    with _generation_lock:
        state = _generation_progress.get(book_id)
        return dict(state) if state else None


def _clear_generation_state(book_id):
    """Remove a book's in-memory generation state if present."""
    with _generation_lock:
        _generation_progress.pop(book_id, None)


def _prune_generation_state(book_id, state=None, assume_locked=False):
    """Drop stale in-memory generation state and return the live value."""
    if assume_locked:
        live_state = _generation_progress.get(book_id)
        if not live_state:
            return None

        age_seconds = (_utcnow() - live_state["last_update"]).total_seconds()
        is_terminal = live_state["status"] in {"completed", "error"}
        max_age = (
            _TERMINAL_STATE_TTL_SECONDS if is_terminal else _GENERATION_STALE_SECONDS
        )

        if age_seconds <= max_age:
            return dict(live_state)

        if state is not None and state.get("last_update") != live_state.get(
            "last_update"
        ):
            return dict(live_state)

        _generation_progress.pop(book_id, None)
        return None

    with _generation_lock:
        return _prune_generation_state(book_id, state=state, assume_locked=True)


def _compute_book_completion_counts(book):
    """Calculate persisted chapter totals and completion counts for a book."""
    topic_ids = [bt.topic_id for bt in book.book_topics]
    if not topic_ids:
        return {
            "needs_generation": False,
            "total_chapters": 0,
            "completed_chapters": 0,
        }

    grouped_counts = (
        db.session.query(
            ChapterMode.topic_id,
            func.count(ChapterMode.id).label("total"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (ChapterMode.content.isnot(None))
                            & (ChapterMode.content != ""),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("completed"),
        )
        .filter(ChapterMode.topic_id.in_(topic_ids))
        .group_by(ChapterMode.topic_id)
        .all()
    )

    counts_by_topic = {
        row.topic_id: {
            "total": int(row.total or 0),
            "completed": int(row.completed or 0),
        }
        for row in grouped_counts
    }

    needs_generation = False
    total_chapters = 0
    completed_chapters = 0

    for topic_id in topic_ids:
        topic_counts = counts_by_topic.get(topic_id)
        if not topic_counts or topic_counts["total"] == 0:
            needs_generation = True
            continue

        total_chapters += topic_counts["total"]
        completed_chapters += topic_counts["completed"]
        if topic_counts["completed"] < topic_counts["total"]:
            needs_generation = True

    return {
        "needs_generation": needs_generation,
        "total_chapters": total_chapters,
        "completed_chapters": completed_chapters,
    }


def _build_progress_response(book, state=None):
    """Build the API payload for current book generation progress."""
    counts = _compute_book_completion_counts(book)
    state = _prune_generation_state(book.id, state)

    if state and state["status"] == "generating":
        phase = state.get("phase", "structuring")
        if phase == "printing":
            total_chapters = max(state.get("planned_total_chapters", 0), 0)
            completed_chapters = min(counts["completed_chapters"], total_chapters)
            progress_percent = int(
                (completed_chapters / total_chapters * 100) if total_chapters else 0
            )
        else:
            total_chapters = 0
            completed_chapters = 0
            progress_percent = 0

        return {
            "book_id": book.id,
            "status": "generating",
            "phase": phase,
            "total_topics": state["total_topics"],
            "current_topic_index": state["current_topic_index"],
            "total_chapters": total_chapters,
            "completed_chapters": completed_chapters,
            "message": state["message"],
            "error": None,
            "progress_percent": progress_percent,
        }

    if state and state["status"] == "error" and counts["needs_generation"]:
        total_chapters = max(
            state.get("planned_total_chapters", counts["total_chapters"]), 0
        )
        completed_chapters = min(counts["completed_chapters"], total_chapters)
        return {
            "book_id": book.id,
            "status": "error",
            "phase": state.get("phase", "structuring"),
            "total_topics": state["total_topics"],
            "current_topic_index": state["current_topic_index"],
            "total_chapters": total_chapters,
            "completed_chapters": completed_chapters,
            "message": state["message"] or "Generation failed",
            "error": state["error"],
            "progress_percent": int(
                (completed_chapters / total_chapters * 100) if total_chapters else 0
            ),
        }

    if counts["needs_generation"]:
        return {
            "status": "pending",
            "phase": "structuring",
            "message": "Ready to generate",
            "book_id": book.id,
            "total_topics": len(book.book_topics),
            "current_topic_index": 0,
            "total_chapters": counts["total_chapters"],
            "completed_chapters": counts["completed_chapters"],
            "error": None,
            "progress_percent": int(
                (counts["completed_chapters"] / counts["total_chapters"] * 100)
                if counts["total_chapters"]
                else 0
            ),
        }

    _clear_generation_state(book.id)
    return {
        "status": "completed",
        "phase": "completed",
        "message": "Already generated",
        "book_id": book.id,
        "total_topics": len(book.book_topics),
        "current_topic_index": len(book.book_topics),
        "total_chapters": counts["total_chapters"],
        "completed_chapters": counts["completed_chapters"],
        "error": None,
        "progress_percent": 100,
    }


def start_book_generation(book_id, user_id, user_background):
    """Start background generation for a book if it still needs content."""
    book = Book.query.get(book_id)
    if not book:
        logger.error(f"Book {book_id} not found")
        return False

    progress_data = _build_progress_response(book)
    if progress_data["status"] == "completed":
        logger.info(f"Book {book_id} is already complete")
        return True

    total_topics = len(book.book_topics)
    with _generation_lock:
        state = _prune_generation_state(book_id, assume_locked=True)
        if state and state["status"] in {"pending", "generating"}:
            logger.info(f"Book {book_id} is already generating")
            return True

        _generation_progress[book_id] = _create_generation_state(
            book_id, user_id, total_topics
        )

    app_context = current_app._get_current_object().app_context()
    thread = Thread(
        target=generate_book_content_background,
        args=(app_context, book_id, user_id, user_background),
    )
    thread.daemon = True
    thread.start()

    return True


def generate_book_content_background(app_context, book_id, user_id, user_background):
    """Generate all content for a book while reporting progress in memory."""
    with app_context:
        try:
            state = _get_generation_state(book_id)
            if not state:
                logger.error(f"Generation state not found for book {book_id}")
                return

            _set_generation_state(
                book_id,
                status="generating",
                phase="structuring",
                planned_total_chapters=0,
                message="Starting generation...",
            )

            book = Book.query.get(book_id)
            if not book:
                raise Exception(f"Book {book_id} not found")

            planner = PlannerAgent()
            teacher = ChapterTeachingAgent()

            total_topics = len(book.book_topics)

            _set_generation_state(
                book_id,
                total_topics=total_topics,
                current_topic_index=0,
                phase="structuring",
                planned_total_chapters=0,
                message="Preparing book structure...",
            )

            for idx, bt in enumerate(
                sorted(book.book_topics, key=lambda x: x.order_index)
            ):
                topic = bt.topic
                _set_generation_state(
                    book_id,
                    current_topic_index=idx,
                    phase="structuring",
                    message=f"Processing topic {idx + 1}/{total_topics}: {topic.name}",
                )

                chapters = (
                    ChapterMode.query.filter_by(topic_id=topic.id)
                    .order_by(ChapterMode.step_index)
                    .all()
                )

                if not chapters:
                    _set_generation_state(
                        book_id, message=f"Generating plan for: {topic.name}"
                    )

                    try:
                        _set_generation_state(
                            book_id,
                            message=f"Generating plan for: {topic.name}",
                        )
                        plan_steps = planner.generate_study_plan(
                            topic.name, user_background
                        )

                        topic.study_plan = plan_steps

                        for i, step_title in enumerate(plan_steps):
                            chapter = ChapterMode(
                                user_id=user_id,
                                topic_id=topic.id,
                                step_index=i,
                                title=step_title,
                            )
                            db.session.add(chapter)

                        db.session.commit()

                        actual_chapters = len(plan_steps)
                        chapters_diff = actual_chapters - 5

                        logger.info(
                            f"Generated plan for {topic.name}: {actual_chapters} chapters (estimate was 5, diff: {chapters_diff})."
                        )

                        chapters = (
                            ChapterMode.query.filter_by(topic_id=topic.id)
                            .order_by(ChapterMode.step_index)
                            .all()
                        )
                    except Exception as e:
                        logger.error(f"Failed to generate plan for {topic.name}: {e}")
                        db.session.rollback()
                        _set_generation_state(
                            book_id,
                            message=f"Error generating plan for {topic.name}: {str(e)}",
                        )
                        continue

            final_structure_counts = _compute_book_completion_counts(book)
            _set_generation_state(
                book_id,
                current_topic_index=0,
                phase="printing",
                planned_total_chapters=final_structure_counts["total_chapters"],
                message="Book structured. Generating chapters...",
            )

            logger.info(
                f"Book {book_id}: Structure ready with {final_structure_counts['total_chapters']} total chapters and {final_structure_counts['completed_chapters']} already complete"
            )

            for idx, bt in enumerate(
                sorted(book.book_topics, key=lambda x: x.order_index)
            ):
                topic = bt.topic
                chapters = (
                    ChapterMode.query.filter_by(topic_id=topic.id)
                    .order_by(ChapterMode.step_index)
                    .all()
                )

                for ch_idx, chapter in enumerate(chapters):
                    if chapter.content:
                        logger.debug(
                            f"Skipping {topic.name} chapter {ch_idx + 1} - already has content"
                        )
                        continue

                    _set_generation_state(
                        book_id,
                        current_topic_index=idx,
                        phase="printing",
                        message=f"Writing {topic.name}: Chapter {ch_idx + 1}/{len(chapters)}",
                    )

                    try:
                        plan_steps = topic.study_plan if topic.study_plan else []
                        step_title = (
                            plan_steps[chapter.step_index]
                            if chapter.step_index < len(plan_steps)
                            else chapter.title or "Chapter Content"
                        )

                        logger.info(
                            f"Generating content for {topic.name} chapter {ch_idx + 1}: {step_title}"
                        )

                        _set_generation_state(
                            book_id,
                            current_topic_index=idx,
                            phase="printing",
                            message=f"Writing {topic.name}: Chapter {ch_idx + 1}/{len(chapters)}",
                        )

                        material = teacher.generate_teaching_material(
                            step_title, plan_steps, user_background, None
                        )

                        chapter.content = material
                        db.session.commit()

                        chapter_counts = _compute_book_completion_counts(book)
                        logger.info(
                            f"Completed {topic.name} chapter {ch_idx + 1}. Progress: {chapter_counts['completed_chapters']}/{chapter_counts['total_chapters']}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to generate content for {topic.name} chapter {chapter.step_index}: {e}"
                        )
                        db.session.rollback()
                        _set_generation_state(
                            book_id,
                            message=f"Error in {topic.name} chapter {ch_idx + 1}: {str(e)}",
                        )

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
                _set_generation_state(book_id, message="Generating book cover...")

                try:
                    _generate_book_cover(book)
                except Exception as cover_err:
                    logger.warning(
                        f"Book cover generation failed for {book_id} (non-fatal): {cover_err}"
                    )

                _set_generation_state(
                    book_id,
                    status="completed",
                    current_topic_index=total_topics,
                    message="Generation complete!",
                    completed_at=_utcnow(),
                    error=None,
                )
                logger.info(f"Book {book_id} generation completed successfully")
            else:
                _set_generation_state(
                    book_id,
                    status="error",
                    message="Some chapters failed to generate",
                    error="Some chapters failed to generate",
                    completed_at=_utcnow(),
                )
                logger.warning(
                    f"Book {book_id} generation incomplete - some chapters failed"
                )

        except Exception as e:
            logger.error(f"Book generation failed for {book_id}: {e}", exc_info=True)
            _set_generation_state(
                book_id,
                status="error",
                message=f"Generation failed: {str(e)}",
                error=str(e),
                completed_at=_utcnow(),
            )


def get_generation_progress(book_id):
    """Return current generation progress for a book."""
    book = Book.query.get(book_id)
    if not book:
        return {"status": "error", "message": "Book not found"}

    return _build_progress_response(book, _get_generation_state(book_id))


def get_all_active_generations(user_id):
    """Return active in-memory book generations for a user."""
    with _generation_lock:
        active_book_ids = [
            book_id
            for book_id, state in _generation_progress.items()
            if state["user_id"] == user_id
            and state["status"] in {"pending", "generating"}
        ]

    return [get_generation_progress(book_id) for book_id in active_book_ids]


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
    data_root = _get_data_root()
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
