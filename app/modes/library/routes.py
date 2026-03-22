from flask import current_app, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app.core.extensions import db
from app.core.models import Book, BookTopic, Topic, ChapterMode
from app.modes.library import library_bp
from app.modes.library.agent import LibrarianAgent
import logging
import os
from app.common.vector_db import VectorDB
from markdown_it import MarkdownIt

logger = logging.getLogger(__name__)
md = MarkdownIt()

# A global/in-memory VectorDB for searching user's topics
# In a real setup, this would be persisted or re-indexed efficiently
vector_db_cache = {}


def _get_book_cover_dir():
    """Return the trusted book cover directory used by generation and serving."""
    data_root = current_app.config.get("DATA_DIR") or current_app.root_path
    return os.path.realpath(os.path.join(data_root, "data", "book_cover"))


def get_user_vector_db(user_id):
    """Initializes and returns the user's vector DB cache."""
    # To keep things light, we rebuild it for the session if it doesn't exist.
    # We use TF-IDF, which is extremely fast for small personal libraries.
    if user_id not in vector_db_cache:
        vdb = VectorDB()
        topics = Topic.query.filter_by(user_id=user_id).all()

        docs = []
        metadata = []
        for t in topics:
            # Combine topic name and its chapter content for rich search context
            content_parts = [t.name]
            # Add chapter content if available (for better semantic matching)
            chapters = ChapterMode.query.filter_by(topic_id=t.id).all()
            for ch in chapters:
                if ch.content:
                    content_parts.append(ch.content)

            full_text = " ".join(content_parts)
            docs.append(full_text)
            metadata.append({"topic_id": t.id, "title": t.name})

        vdb.add_documents(docs, metadata)
        vector_db_cache[user_id] = vdb

    return vector_db_cache[user_id]


def _book_needs_generation(book, progress_status):
    """Return whether a book still needs generated chapter content."""
    if progress_status in ["completed", "generating"]:
        return False

    for bt in book.book_topics:
        chapters = bt.topic.chapter_mode
        if not chapters:
            return True
        if any(not ch.content or not ch.content.strip() for ch in chapters):
            return True

    return False


def _resolve_cover_path(candidate_path):
    """Resolve a cover path and ensure it stays inside the trusted cover dir."""
    if not candidate_path:
        return None

    book_cover_dir = _get_book_cover_dir()
    target_path = candidate_path
    if os.path.isabs(target_path) and not os.path.exists(target_path):
        filename = os.path.basename(target_path)
        fallback_path = os.path.join(book_cover_dir, filename)
        if os.path.exists(fallback_path):
            target_path = fallback_path

    if not os.path.isabs(target_path):
        target_path = os.path.join(current_app.root_path, target_path)

    target_realpath = os.path.realpath(os.path.abspath(os.path.normpath(target_path)))
    if os.path.commonpath([book_cover_dir, target_realpath]) != book_cover_dir:
        return None

    return target_realpath


def _prepare_dashboard_data(skip_shared=False):
    """Helper to prepare book progress and needs_generation data for the dashboard."""
    my_books = (
        Book.query.filter_by(user_id=current_user.userid)
        .order_by(Book.created_at.desc())
        .all()
    )
    # Discover others' shared books
    shared_books = []
    if not skip_shared:
        shared_books = (
            Book.query.filter_by(is_shared=True)
            .filter(Book.user_id != current_user.userid)
            .order_by(Book.modified_at.desc())
            .limit(20)
            .all()
        )

    from app.modes.library.agent import get_generation_progress

    book_progress = {}
    book_needs_generation = {}

    for book in my_books:
        progress_data = get_generation_progress(book.id)
        needs_generation = _book_needs_generation(book, progress_data["status"])

        book_needs_generation[book.id] = needs_generation
        if progress_data["status"] == "generating":
            book_progress[book.id] = progress_data

    return my_books, shared_books, book_progress, book_needs_generation


@library_bp.route("/")
@login_required
def dashboard():
    """Renders the main Library Dashboard."""
    my_books, shared_books, book_progress, book_needs_generation = (
        _prepare_dashboard_data()
    )
    return render_template(
        "library/library_dashboard.html",
        my_books=my_books,
        shared_books=shared_books,
        book_progress=book_progress,
        book_needs_generation=book_needs_generation,
    )


@library_bp.route("/my-books-fragment")
@login_required
def my_books_fragment():
    """Returns the HTML fragment for the 'My Books' grid."""
    my_books, _, book_progress, book_needs_generation = _prepare_dashboard_data(
        skip_shared=True
    )
    return render_template(
        "library/_my_books_grid.html",
        my_books=my_books,
        book_progress=book_progress,
        book_needs_generation=book_needs_generation,
    )


@library_bp.route("/card/<int:book_id>")
@login_required
def book_card_fragment(book_id):
    """Returns the HTML fragment for a single book card."""
    book = Book.query.get_or_404(book_id)
    if book.user_id != current_user.userid and not book.is_shared:
        return "Unauthorized", 403

    from app.modes.library.agent import get_generation_progress

    progress_data = get_generation_progress(book.id)

    needs_generation = _book_needs_generation(book, progress_data["status"])

    return render_template(
        "library/_book_card.html",
        book=book,
        progress_data=progress_data
        if progress_data["status"] == "generating"
        else None,
        needs_generation=needs_generation,
    )


@library_bp.route("/search", methods=["GET"])
@login_required
def search_library():
    """Searches the user's existing topics using VectorDB to curate a book."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400

    vdb = get_user_vector_db(current_user.userid)
    current_topics = Topic.query.filter_by(user_id=current_user.userid).all()

    agent = LibrarianAgent()
    suggestion = agent.search_and_suggest(query, vdb, current_topics)

    if not suggestion:
        return jsonify(
            {
                "message": "No relevant existing content found. Consider generating a new book."
            }
        ), 404

    return jsonify(suggestion)


@library_bp.route("/generate", methods=["POST"])
@login_required
def generate_book():
    """Generates a new book structure using Agentic planning."""
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "Query required"}), 400

    user_bg = (
        current_user.user_profile.to_context_string()
        if current_user.user_profile
        else "A beginner"
    )
    agent = LibrarianAgent()
    book_plan = agent.generate_book(query, user_bg)

    # Actually create the shell book and topics in DB
    try:
        new_book = Book(
            user_id=current_user.userid,
            title=book_plan.get("title", f"Book on {query}"),
            description=book_plan.get("description", ""),
            is_shared=False,
        )
        db.session.add(new_book)
        db.session.flush()  # Get new_book IDs

        # Create empty Topics for each chapter in the plan
        for idx, topic_title in enumerate(book_plan.get("topics", [])):
            t = Topic(name=topic_title, user_id=current_user.userid)
            db.session.add(t)
            db.session.flush()  # Get t.id

            bt = BookTopic(book_id=new_book.id, topic_id=t.id, order_index=idx)
            db.session.add(bt)

        db.session.commit()
        # Invalidate vector DB cache
        if current_user.userid in vector_db_cache:
            del vector_db_cache[current_user.userid]

        return jsonify(
            {
                "success": True,
                "book": {"id": new_book.id, "title": new_book.title},
                "redirect": url_for(
                    "library.read_book", book_id=new_book.id, page_num=1
                ),
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/create-from-suggestion", methods=["POST"])
@login_required
def create_from_suggestion():
    """Creates a book containing the curated existing topics."""
    data = request.json
    title = data.get("title")
    desc = data.get("description")
    topic_ids = data.get("topic_ids", [])

    if not title or not topic_ids:
        return jsonify({"error": "Invalid data"}), 400

    try:
        b = Book(
            user_id=current_user.userid, title=title, description=desc, is_shared=False
        )
        db.session.add(b)
        db.session.flush()

        for idx, tid in enumerate(topic_ids):
            # Verify user owns topic
            t = Topic.query.filter_by(id=tid, user_id=current_user.userid).first()
            if t:
                bt = BookTopic(book_id=b.id, topic_id=t.id, order_index=idx)
                db.session.add(bt)

        db.session.commit()
        return jsonify({"success": True, "book_id": b.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/progress")
@login_required
def generation_progress(book_id):
    """Returns the current progress of the background generation process."""
    book = Book.query.get_or_404(book_id)
    if book.user_id != current_user.userid and not book.is_shared:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    # Use the new database-backed progress system
    from app.modes.library.agent import get_generation_progress

    progress_data = get_generation_progress(book_id)
    return jsonify(progress_data)


@library_bp.route("/<int:book_id>/init", methods=["POST", "GET"])
@login_required
def init_book(book_id):
    """
    Spawns background generation for the book if it is not completely generated.
    Returns JSON describing the status, allowing the frontend to poll /progress.
    """
    book = Book.query.get_or_404(book_id)

    if book.user_id != current_user.userid and not book.is_shared:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    from app.common.utils import get_user_context
    from app.modes.library.agent import start_book_generation, get_generation_progress

    user_background = get_user_context()

    # Check current progress
    progress_data = get_generation_progress(book_id)

    if progress_data["status"] == "completed":
        return jsonify(
            {
                "status": "ready",
                "redirect": url_for("library.read_book", book_id=book.id, page_num=1),
            }
        )

    if progress_data["status"] == "generating":
        return jsonify(progress_data)

    # Status is 'pending' or 'error' - start/restart generation
    if progress_data["status"] in ["pending", "error"]:
        success = start_book_generation(book_id, current_user.userid, user_background)

        if success:
            return jsonify(get_generation_progress(book_id))
        else:
            return jsonify({"status": "error", "message": "Failed to start generation"})

    # Fallback
    return jsonify(progress_data)


@library_bp.route("/<int:book_id>/page/<int:page_num>")
@login_required
def read_book(book_id, page_num):
    """
    Paginated Book View Interface.
    Maps page_num to the flattened list of chapters across all topics in the book.
    """
    book = Book.query.get_or_404(book_id)

    # Check permissions
    if book.user_id != current_user.userid and not book.is_shared:
        return render_template(
            "error.html", error_message="You don't have permission to view this book."
        ), 403

    # Get all ordered topics in the book
    book_topics = sorted(book.book_topics, key=lambda x: x.order_index)
    topics = [bt.topic for bt in book_topics]

    # For pagination, we flatten chapters from topics (Page 1 = Topic1/Chapter1... )
    # This requires looking up all chapters for these topics.
    flattened_pages = []

    for topic_idx, t in enumerate(topics):
        chapters = (
            ChapterMode.query.filter_by(topic_id=t.id)
            .order_by(ChapterMode.step_index)
            .all()
        )
        # If no chapters yet, we treat the topic itself as a pending 1-page placeholder
        if not chapters:
            flattened_pages.append(
                {
                    "type": "placeholder",
                    "topic": t,
                    "topic_number": topic_idx + 1,
                    "chapter": None,
                    "global_page": len(flattened_pages) + 1,
                }
            )
        else:
            for ch in chapters:
                flattened_pages.append(
                    {
                        "type": "content",
                        "topic": t,
                        "topic_number": topic_idx + 1,
                        "chapter": ch,
                        "global_page": len(flattened_pages) + 1,
                    }
                )

    total_pages = len(flattened_pages)

    if page_num < 1 or page_num > total_pages:
        if total_pages == 0:
            return render_template(
                "library/book_view.html",
                book=book,
                current_page_data=None,
                page_num=0,
                total_pages=0,
            )
        return redirect(
            url_for(
                "library.read_book",
                book_id=book.id,
                page_num=max(1, min(page_num, total_pages)),
            )
        )

    current_page_data = flattened_pages[page_num - 1]

    # Convert markdown to html if this is a content page
    if current_page_data["type"] == "content" and current_page_data["chapter"].content:
        # We need a copy or attribute to store rendered html so we don't save raw html to DB
        current_page_data["chapter_html"] = md.render(
            current_page_data["chapter"].content
        )
    else:
        current_page_data["chapter_html"] = ""

    # Handle Notes exposure
    # Determine note visibility and ownership
    is_owner = book.user_id == current_user.userid
    show_notes = is_owner or (book.is_shared and book.notes_shared)
    notes_are_shared = book.is_shared and book.notes_shared and not is_owner
    owner_name = book.login.display_name if book.login else "Book Owner"

    return render_template(
        "library/book_view.html",
        book=book,
        all_pages=flattened_pages,
        current_page_data=current_page_data,
        page_num=page_num,
        total_pages=total_pages,
        show_notes=show_notes,
        is_owner=is_owner,
        notes_are_shared=notes_are_shared,
        owner_name=owner_name,
    )


@library_bp.route("/<int:book_id>/toggle-share", methods=["POST"])
@login_required
def toggle_share(book_id):
    """Toggles the is_shared status of a book."""
    book = Book.query.get_or_404(book_id)
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    book.is_shared = data.get("is_shared", False)

    # If book is being un-shared, automatically disable note sharing
    if not book.is_shared:
        book.notes_shared = False

    db.session.commit()

    return jsonify({"success": True, "is_shared": book.is_shared})


@library_bp.route("/<int:book_id>/toggle-notes-share", methods=["POST"])
@login_required
def toggle_notes_share(book_id):
    """Toggles the notes_shared status of a book."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can toggle
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    notes_shared = data.get("notes_shared", False)

    # Validation: notes_shared requires is_shared
    if notes_shared and not book.is_shared:
        return jsonify({"error": "Cannot share notes when book is not shared"}), 400

    book.notes_shared = notes_shared
    db.session.commit()

    return jsonify({"success": True, "notes_shared": book.notes_shared})


@library_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    """Deletes a book owned by the current user."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can delete
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Store cover path for deletion after DB deletion
        cover_to_delete = book.cover_path

        # Delete the book (cascade will handle book_topics)
        db.session.delete(book)
        db.session.commit()

        # Delete cover file if it exists
        if cover_to_delete:
            target_path = _resolve_cover_path(cover_to_delete)
            if not target_path:
                logger.warning(
                    "Skipping book cover deletion outside trusted directory: %s",
                    cover_to_delete,
                )
            elif os.path.exists(target_path):
                try:
                    os.remove(target_path)
                    logger.info(f"Deleted book cover file: {target_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete cover file {target_path}: {e}")

        # Invalidate vector DB cache
        if current_user.userid in vector_db_cache:
            del vector_db_cache[current_user.userid]

        return jsonify({"success": True, "message": "Book deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/retry_cover", methods=["POST"])
@login_required
def retry_cover(book_id):
    """Retries book cover generation for a book."""
    book = Book.query.get_or_404(book_id)

    # Allow owner or shared book viewers to trigger retry
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        from app.modes.library.agent import _generate_book_cover

        _generate_book_cover(book)

        if book.cover_path:
            return jsonify(
                {
                    "success": True,
                    "cover_url": url_for("library.serve_cover", book_id=book.id),
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Cover generation failed. Is ComfyUI running?",
                }
            ), 500
    except Exception as e:
        logger.error(f"Cover retry failed for book {book_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@library_bp.route("/<int:book_id>/cover")
@login_required
def serve_cover(book_id):
    """Serves the book cover image file."""
    from flask import send_file

    book = Book.query.get_or_404(book_id)

    # Allow access if owner or if book is shared
    if book.user_id != current_user.userid and not book.is_shared:
        return "Unauthorized", 403

    if not book.cover_path:
        return "Cover not set", 404

    target_path = _resolve_cover_path(book.cover_path)
    if not target_path:
        logger.warning(
            f"Rejected cover path outside trusted directory: {book.cover_path}"
        )
        return "Cover file not found", 404

    if not os.path.exists(target_path):
        logger.warning(
            f"Cover file not found at: {target_path} (Original DB path: {book.cover_path})"
        )
        return "Cover file not found", 404

    return send_file(target_path, mimetype="image/png")


@library_bp.route("/<int:book_id>/edit", methods=["GET"])
@login_required
def edit_book(book_id):
    """Renders the book editing interface."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return render_template(
            "error.html", error_message="You don't have permission to edit this book."
        ), 403

    # Get all user's topics for adding to book
    user_topics = Topic.query.filter_by(user_id=current_user.userid).all()

    # Get topics already in the book
    book_topic_ids = [bt.topic_id for bt in book.book_topics]

    return render_template(
        "library/library_edit.html",
        book=book,
        user_topics=user_topics,
        book_topic_ids=book_topic_ids,
    )


@library_bp.route("/<int:book_id>/update-metadata", methods=["POST"])
@login_required
def update_book_metadata(book_id):
    """Updates book title and description."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()

    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        book.title = title
        book.description = description
        db.session.commit()
        return jsonify({"success": True, "message": "Book updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/add-topic", methods=["POST"])
@login_required
def add_topic_to_book(book_id):
    """Adds an existing topic to the book."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topic_id = data.get("topic_id")

    if not topic_id:
        return jsonify({"error": "Topic ID is required"}), 400

    # Verify user owns the topic
    topic = Topic.query.filter_by(id=topic_id, user_id=current_user.userid).first()
    if not topic:
        return jsonify({"error": "Topic not found or unauthorized"}), 404

    # Check if topic is already in the book
    existing = BookTopic.query.filter_by(book_id=book_id, topic_id=topic_id).first()
    if existing:
        return jsonify({"error": "Topic already in book"}), 400

    try:
        # Get the max order_index and add 1
        max_order = (
            db.session.query(db.func.max(BookTopic.order_index))
            .filter_by(book_id=book_id)
            .scalar()
            or -1
        )

        bt = BookTopic(book_id=book_id, topic_id=topic_id, order_index=max_order + 1)
        db.session.add(bt)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Topic added successfully",
                "topic": {"id": topic.id, "name": topic.name},
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/remove-topic/<int:topic_id>", methods=["POST"])
@login_required
def remove_topic_from_book(book_id, topic_id):
    """Removes a topic from the book."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    # Find the BookTopic association
    bt = BookTopic.query.filter_by(book_id=book_id, topic_id=topic_id).first()
    if not bt:
        return jsonify({"error": "Topic not in book"}), 404

    try:
        db.session.delete(bt)

        # Reorder remaining topics
        remaining_topics = (
            BookTopic.query.filter_by(book_id=book_id)
            .order_by(BookTopic.order_index)
            .all()
        )
        for idx, topic in enumerate(remaining_topics):
            topic.order_index = idx

        db.session.commit()
        return jsonify({"success": True, "message": "Topic removed successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/reorder-topics", methods=["POST"])
@login_required
def reorder_topics(book_id):
    """Reorders topics in the book."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topic_ids = data.get("topic_ids", [])

    if not topic_ids:
        return jsonify({"error": "Topic IDs are required"}), 400

    try:
        # Update order_index for each topic
        for idx, topic_id in enumerate(topic_ids):
            bt = BookTopic.query.filter_by(book_id=book_id, topic_id=topic_id).first()
            if bt:
                bt.order_index = idx

        db.session.commit()
        return jsonify({"success": True, "message": "Topics reordered successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/apply-ai-suggestions", methods=["POST"])
@login_required
def apply_ai_suggestions(book_id):
    """Applies AI suggestions to add/remove topics from the book."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topics_to_add = data.get("add", [])  # List of topic IDs
    topics_to_remove = data.get("remove", [])  # List of topic IDs
    update_description = data.get("update_description", False)

    try:
        # Get current book topics
        current_topic_ids = [bt.topic_id for bt in book.book_topics]

        # Remove topics
        for topic_id in topics_to_remove:
            if topic_id in current_topic_ids:
                bt = BookTopic.query.filter_by(
                    book_id=book_id, topic_id=topic_id
                ).first()
                if bt:
                    db.session.delete(bt)

        # Add topics
        for topic_id in topics_to_add:
            if topic_id not in current_topic_ids:
                # Verify user owns the topic
                topic = Topic.query.filter_by(
                    id=topic_id, user_id=current_user.userid
                ).first()
                if topic:
                    # Get the max order_index and add 1
                    max_order = (
                        db.session.query(db.func.max(BookTopic.order_index))
                        .filter_by(book_id=book_id)
                        .scalar()
                        or -1
                    )

                    bt = BookTopic(
                        book_id=book_id, topic_id=topic_id, order_index=max_order + 1
                    )
                    db.session.add(bt)

        # Reorder remaining topics
        remaining_topics = (
            BookTopic.query.filter_by(book_id=book_id)
            .order_by(BookTopic.order_index)
            .all()
        )
        for idx, topic in enumerate(remaining_topics):
            topic.order_index = idx

        # Update description if requested
        if update_description and (topics_to_add or topics_to_remove):
            from app.common.utils import call_llm
            from app.modes.library.prompts import get_book_description_prompt

            # Get updated topic list
            updated_topics = [bt.topic for bt in remaining_topics]
            topic_names = [t.name for t in updated_topics]

            if topic_names:
                prompt = get_book_description_prompt(book.title, topic_names)
                new_description = call_llm(prompt, is_json=False)
                book.description = new_description.strip()

        db.session.commit()

        message = f"Applied changes: {len(topics_to_add)} added, {len(topics_to_remove)} removed"
        if update_description and (topics_to_add or topics_to_remove):
            message += ". Book description updated."

        return jsonify({"success": True, "message": message})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error applying AI suggestions: {e}")
        return jsonify({"error": str(e)}), 500


@library_bp.route("/<int:book_id>/ai-update", methods=["POST"])
@login_required
def ai_update_book(book_id):
    """Uses AI to suggest topics to add/remove based on a query."""
    book = Book.query.get_or_404(book_id)

    # Authorization: Only book owner can edit
    if book.user_id != current_user.userid:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        from app.common.utils import call_llm
        from app.modes.library.prompts import get_book_update_prompt

        # Get user's topics
        user_topics = Topic.query.filter_by(user_id=current_user.userid).all()

        # Get current book topics
        current_topics = [bt.topic for bt in book.book_topics]

        # Build lists for prompt
        current_topic_names = [t.name for t in current_topics]
        all_topic_names = [t.name for t in user_topics]

        # Get prompt from prompts file
        prompt = get_book_update_prompt(
            book_title=book.title,
            book_description=book.description,
            current_topics=current_topic_names,
            all_topics=all_topic_names,
            user_query=query,
        )

        response = call_llm(prompt, is_json=True)

        # Parse response
        suggestions_data = response if isinstance(response, dict) else {}
        add_names = suggestions_data.get("add", [])
        remove_names = suggestions_data.get("remove", [])
        reasoning = suggestions_data.get("reasoning", "")

        # Map topic names to IDs
        topic_name_to_id = {t.name: t.id for t in user_topics}

        topics_to_add = []
        for name in add_names:
            if name in topic_name_to_id:
                topic_id = topic_name_to_id[name]
                # Only add if not already in book
                if topic_id not in [t.id for t in current_topics]:
                    topic = next((t for t in user_topics if t.id == topic_id), None)
                    if topic:
                        topics_to_add.append({"id": topic.id, "name": topic.name})

        topics_to_remove = []
        for name in remove_names:
            if name in topic_name_to_id:
                topic_id = topic_name_to_id[name]
                # Only remove if currently in book
                if topic_id in [t.id for t in current_topics]:
                    topic = next((t for t in current_topics if t.id == topic_id), None)
                    if topic:
                        topics_to_remove.append({"id": topic.id, "name": topic.name})

        return jsonify(
            {
                "success": True,
                "suggestions": {
                    "add": topics_to_add,
                    "remove": topics_to_remove,
                    "message": reasoning,
                },
            }
        )
    except Exception as e:
        logger.error(f"AI update error: {e}")
        return jsonify({"error": str(e)}), 500
