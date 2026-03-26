import uuid
import sys
from unittest.mock import MagicMock
import os

import pytest

sys.modules.setdefault("bleach", MagicMock())

from app.core.models import Book, BookTopic, ChapterMode, Login, Topic, db
from app.modes.library import agent as library_agent


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_generation_state():
    library_agent._generation_progress.clear()
    yield
    library_agent._generation_progress.clear()


def _create_book(app, with_content=False):
    with app.app_context():
        login = Login.query.filter_by(username="testuser").first()
        suffix = uuid.uuid4().hex[:8]

        topic = Topic(user_id=login.userid, name=f"Library Topic {suffix}")
        book = Book(
            user_id=login.userid,
            title=f"Library Book {suffix}",
            description="Test book",
            is_shared=False,
        )
        db.session.add(topic)
        db.session.add(book)
        db.session.flush()

        db.session.add(BookTopic(book_id=book.id, topic_id=topic.id, order_index=0))

        if with_content:
            db.session.add(
                ChapterMode(
                    user_id=login.userid,
                    topic_id=topic.id,
                    step_index=0,
                    title="Intro",
                    content="Ready",
                )
            )

        db.session.commit()
        return book.id, login.userid


def _create_book_with_topics(app, topic_count=1):
    with app.app_context():
        login = Login.query.filter_by(username="testuser").first()
        suffix = uuid.uuid4().hex[:8]

        book = Book(
            user_id=login.userid,
            title=f"Library Book {suffix}",
            description="Test book",
            is_shared=False,
        )
        db.session.add(book)
        db.session.flush()

        topic_ids = []
        for order_index in range(topic_count):
            topic = Topic(
                user_id=login.userid,
                name=f"Library Topic {suffix}-{order_index}",
            )
            db.session.add(topic)
            db.session.flush()
            topic_ids.append(topic.id)
            db.session.add(
                BookTopic(book_id=book.id, topic_id=topic.id, order_index=order_index)
            )

        db.session.commit()
        return book.id, login.userid, topic_ids


def test_progress_endpoint_returns_pending_without_db_progress(auth_client, app):
    book_id, _ = _create_book(app)

    response = auth_client.get(f"/library/{book_id}/progress")

    assert response.status_code == 200
    assert response.json["status"] == "pending"
    assert response.json["message"] == "Ready to generate"
    assert response.json["book_id"] == book_id


def test_progress_endpoint_uses_in_memory_generation_state(auth_client, app):
    book_id, user_id = _create_book(app)
    state = library_agent._create_generation_state(book_id, user_id, total_topics=1)
    state["status"] = "generating"
    state["message"] = "Writing chapter 1"
    library_agent._generation_progress[book_id] = state

    response = auth_client.get(f"/library/{book_id}/progress")

    assert response.status_code == 200
    assert response.json["status"] == "generating"
    assert response.json["message"] == "Writing chapter 1"
    assert response.json["book_id"] == book_id


def test_init_endpoint_returns_ready_for_completed_book(auth_client, app):
    book_id, _ = _create_book(app, with_content=True)

    response = auth_client.post(f"/library/{book_id}/init")

    assert response.status_code == 200
    assert response.json["status"] == "ready"
    assert response.json["redirect"] == f"/library/{book_id}/page/1"


def test_init_get_returns_ready_for_completed_book(auth_client, app):
    book_id, _ = _create_book(app, with_content=True)

    response = auth_client.get(f"/library/{book_id}/init")

    assert response.status_code == 200
    assert response.json["status"] == "ready"
    assert response.json["redirect"] == f"/library/{book_id}/page/1"


def test_cover_route_reads_cover_from_project_data_directory(
    auth_client, app, tmp_path
):
    book_id, _ = _create_book(app, with_content=True)

    with app.app_context():
        app.config["DATA_DIR"] = str(tmp_path)
        book = Book.query.get(book_id)
        cover_dir = os.path.join(app.config["DATA_DIR"], "data", "book_cover")
        os.makedirs(cover_dir, exist_ok=True)
        cover_path = os.path.join(cover_dir, f"test_cover_{book_id}.png")

        with open(cover_path, "wb") as cover_file:
            cover_file.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        book.cover_path = f"data/book_cover/test_cover_{book_id}.png"
        db.session.commit()

    response = auth_client.get(f"/library/{book_id}/cover")

    assert response.status_code == 200
    assert response.mimetype == "image/png"


def test_init_post_starts_generation_for_pending_book(auth_client, app, mocker):
    book_id, user_id = _create_book(app)

    mocker.patch(
        "app.common.utils.get_user_context",
        return_value="A beginner",
    )
    start_generation = mocker.patch(
        "app.modes.library.agent.start_book_generation",
        return_value=True,
    )
    mocker.patch(
        "app.modes.library.agent.get_generation_progress",
        side_effect=[
            {
                "status": "pending",
                "message": "Ready to generate",
                "book_id": book_id,
                "total_chapters": 0,
                "completed_chapters": 0,
            },
            {
                "status": "generating",
                "message": "Starting generation...",
                "book_id": book_id,
                "total_chapters": 0,
                "completed_chapters": 0,
            },
        ],
    )

    response = auth_client.post(f"/library/{book_id}/init")

    assert response.status_code == 200
    assert response.json["status"] == "generating"
    start_generation.assert_called_once_with(book_id, user_id, "A beginner")


def test_progress_hides_chapter_total_during_structuring(auth_client, app):
    book_id, user_id, topic_ids = _create_book_with_topics(app, topic_count=2)

    with app.app_context():
        db.session.add(
            ChapterMode(
                user_id=user_id,
                topic_id=topic_ids[0],
                step_index=0,
                title="Intro",
                content="Done",
            )
        )
        db.session.commit()

    state = library_agent._create_generation_state(book_id, user_id, total_topics=2)
    state["status"] = "generating"
    state["phase"] = "structuring"
    state["message"] = "Generating plan for topic 2"
    library_agent._generation_progress[book_id] = state

    response = auth_client.get(f"/library/{book_id}/progress")

    assert response.status_code == 200
    assert response.json["status"] == "generating"
    assert response.json["phase"] == "structuring"
    assert response.json["total_chapters"] == 0
    assert response.json["completed_chapters"] == 0


def test_progress_uses_fixed_total_chapters_during_printing(auth_client, app):
    book_id, user_id, topic_ids = _create_book_with_topics(app, topic_count=2)

    with app.app_context():
        db.session.add_all(
            [
                ChapterMode(
                    user_id=user_id,
                    topic_id=topic_ids[0],
                    step_index=0,
                    title="Intro",
                    content="Done",
                ),
                ChapterMode(
                    user_id=user_id,
                    topic_id=topic_ids[0],
                    step_index=1,
                    title="Advanced",
                    content="Done",
                ),
                ChapterMode(
                    user_id=user_id,
                    topic_id=topic_ids[1],
                    step_index=0,
                    title="New 1",
                    content=None,
                ),
                ChapterMode(
                    user_id=user_id,
                    topic_id=topic_ids[1],
                    step_index=1,
                    title="New 2",
                    content=None,
                ),
                ChapterMode(
                    user_id=user_id,
                    topic_id=topic_ids[1],
                    step_index=2,
                    title="Unexpected extra",
                    content=None,
                ),
            ]
        )
        db.session.commit()

    state = library_agent._create_generation_state(book_id, user_id, total_topics=2)
    state["status"] = "generating"
    state["phase"] = "printing"
    state["planned_total_chapters"] = 4
    state["message"] = "Writing Topic 2: Chapter 1/2"
    library_agent._generation_progress[book_id] = state

    response = auth_client.get(f"/library/{book_id}/progress")

    assert response.status_code == 200
    assert response.json["status"] == "generating"
    assert response.json["phase"] == "printing"
    assert response.json["total_chapters"] == 4
    assert response.json["completed_chapters"] == 2
