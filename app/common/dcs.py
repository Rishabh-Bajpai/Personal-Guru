import os
import requests
import logging
import threading
import time
from app.core.extensions import db
from app.core.models import Installation, Topic, ChatMode, ChapterMode, QuizMode, FlashcardMode, User, TelemetryLog, Feedback, AIModelPerformance, PlanRevision, SyncLog

logger = logging.getLogger(__name__)

DCS_BASE_URL = os.getenv("DCS_BASE_URL", "https://telemetry.samosa-ai.com")

class DCSClient:
    """Client for communicating with the Data Collection Server (DCS)."""

    def __init__(self):
        """Initialize DCS client with base URL and load installation ID."""
        self.base_url = DCS_BASE_URL
        self.installation_id = None
        self._load_installation_id()

    def _load_installation_id(self):
        """Load installation ID from database if available."""
        try:
            from app.core.models import Installation
            inst = Installation.query.first()
            if inst:
                self.installation_id = inst.installation_id
        except Exception:
            # DB might not be ready
            pass

    def register_device(self):
        """
        Registers the device with the DCS.
        If already registered (ID exists in DB), verifies or updates details.
        """
        from app.common.utils import get_system_info
        from sqlalchemy.exc import OperationalError

        # Check if already registered
        try:
            inst = Installation.query.first()
            if inst:
                self.installation_id = inst.installation_id
                logger.info(f"Device already registered with ID: {self.installation_id}")
                # Optionally update details
                self.update_device_details()
                return True
        except OperationalError:
            logger.warning("Database tables not ready yet. Retrying registration later.")
            return False
        except Exception as e:
            logger.error(f"Error checking registration: {e}")
            return False

        logger.info("Registering device with DCS...")
        try:
            # Step 1: Request Identity
            resp = requests.post(f"{self.base_url}/api/register", json={}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            new_id = data.get("installation_id")

            if not new_id:
                logger.error("DCS did not return installation_id")
                return False

            self.installation_id = new_id

            # Step 2: Save to DB
            sys_info = get_system_info()
            new_inst = Installation(
                installation_id=new_id,
                cpu_cores=sys_info['cpu_cores'],
                ram_gb=sys_info['ram_gb'],
                gpu_model=sys_info['gpu_model'],
                os_version=sys_info['os_version'],
                install_method=sys_info['install_method']
            )
            db.session.add(new_inst)
            db.session.commit()

            logger.info(f"Device registered successfully: {new_id}")

            # Step 3: Update details immediately
            self.update_device_details()
            return True

        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return False

    def update_device_details(self):
        """Send updated device details to DCS server."""
        if not self.installation_id:
            return False

        from app.common.utils import get_system_info
        sys_info = get_system_info()
        payload = sys_info.copy()
        payload['installation_id'] = self.installation_id

        try:
            resp = requests.post(f"{self.base_url}/api/register/update", json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to update device details: {e}")
            return False

    def sync_data(self):
        """
        Gathers unsynced data and sends it to DCS.
        """
        if not self.installation_id:
            logger.warning("Cannot sync: No installation_id")
            return

        payload = {
            "installation_id": self.installation_id,
            "installations": [],
            "topics": [],
            "chat_modes": [],
            "chapter_modes": [],
            "quiz_modes": [],
            "flashcard_modes": [],
            "user_profiles": [],
            "plan_revisions": [],
            "ai_performances": [],
            "telemetry_events": [],
            "feedback": []
        }

        BATCH_SIZE = 50
        objects_to_update = []

        # Track which topics are included in this payload
        included_topic_ids = set()

        def add_topic_to_payload(topic):
            if topic.id in included_topic_ids:
                return
            payload["topics"].append({
                "id": topic.id,
                "user_id": topic.user_id,
                "name": topic.name,
                "study_plan": topic.study_plan,
                "created_at": topic.created_at.isoformat(),
                "modified_at": topic.modified_at.isoformat()
            })
            included_topic_ids.add(topic.id)

        try:
            # 0. Installations (Pending)
            installations = Installation.query.filter((Installation.sync_status == 'pending') | (Installation.sync_status is None)).limit(BATCH_SIZE).all()
            for inst in installations:
                payload["installations"].append({
                    "installation_id": inst.installation_id,
                    "cpu_cores": inst.cpu_cores,
                    "ram_gb": inst.ram_gb,
                    "gpu_model": inst.gpu_model,
                    "os_version": inst.os_version,
                    "install_method": inst.install_method,
                    "created_at": inst.created_at.isoformat(),
                    "modified_at": inst.modified_at.isoformat()
                })
                objects_to_update.append(inst)

            # 1. Topics (Pending)
            topics = Topic.query.filter((Topic.sync_status == 'pending') | (Topic.sync_status is None)).limit(BATCH_SIZE).all()
            for t in topics:
                add_topic_to_payload(t)
                objects_to_update.append(t)

            # 2. Child Objects - Ensure Parent Topic is Included

            # ChatMode
            chats = ChatMode.query.filter((ChatMode.sync_status == 'pending') | (ChatMode.sync_status is None)).limit(BATCH_SIZE).all()
            for c in chats:
                payload["chat_modes"].append({
                    "topic_id": c.topic_id,
                    "user_id": c.user_id,
                    "history": c.history,
                    "history_summary": c.history_summary,
                    "popup_chat_history": c.popup_chat_history,
                    "time_spent": c.time_spent,
                    "created_at": c.created_at.isoformat(),
                    "modified_at": c.modified_at.isoformat()
                })
                objects_to_update.append(c)
                # Ensure parent topic is added
                if c.topic and c.topic.id not in included_topic_ids:
                    add_topic_to_payload(c.topic)

            # ChapterMode
            chapters = ChapterMode.query.filter((ChapterMode.sync_status == 'pending') | (ChapterMode.sync_status is None)).limit(BATCH_SIZE).all()
            for c in chapters:
                payload["chapter_modes"].append({
                    "topic_id": c.topic_id,
                    "user_id": c.user_id,
                    "step_index": c.step_index,
                    "title": c.title,
                    "content": c.content,
                    "podcast_audio_path": c.podcast_audio_path,
                    "questions": c.questions,
                    "user_answers": c.user_answers,
                    "score": c.score,
                    "popup_chat_history": c.popup_chat_history,
                    "time_spent": c.time_spent or 0,
                    "created_at": c.created_at.isoformat(),
                    "modified_at": c.modified_at.isoformat()
                })
                objects_to_update.append(c)
                if c.topic and c.topic.id not in included_topic_ids:
                    add_topic_to_payload(c.topic)

            # QuizMode
            quizzes = QuizMode.query.filter((QuizMode.sync_status == 'pending') | (QuizMode.sync_status is None)).limit(BATCH_SIZE).all()
            for q in quizzes:
                payload["quiz_modes"].append({
                    "topic_id": q.topic_id,
                    "user_id": q.user_id,
                    "questions": q.questions,
                    "score": q.score,
                    "result": q.result,
                    "time_spent": q.time_spent or 0,
                    "created_at": q.created_at.isoformat(),
                    "modified_at": q.modified_at.isoformat()
                })
                objects_to_update.append(q)
                if q.topic and q.topic.id not in included_topic_ids:
                    add_topic_to_payload(q.topic)

            # FlashcardMode
            flashcards = FlashcardMode.query.filter((FlashcardMode.sync_status == 'pending') | (FlashcardMode.sync_status is None)).limit(BATCH_SIZE).all()
            for f in flashcards:
                payload["flashcard_modes"].append({
                    "topic_id": f.topic_id,
                    "user_id": f.user_id,
                    "term": f.term,
                    "definition": f.definition,
                    "time_spent": f.time_spent,
                    "created_at": f.created_at.isoformat(),
                    "modified_at": f.modified_at.isoformat()
                })
                objects_to_update.append(f)
                if f.topic and f.topic.id not in included_topic_ids:
                    add_topic_to_payload(f.topic)

            # User Profile
            users = User.query.filter((User.sync_status == 'pending') | (User.sync_status is None)).limit(BATCH_SIZE).all()
            for u in users:
                payload["user_profiles"].append({
                    "login_id": u.login_id,
                    "age": u.age,
                    "country": u.country,
                    "languages": u.languages,
                    "education_level": u.education_level,
                    "field_of_study": u.field_of_study,
                    "occupation": u.occupation,
                    "learning_goals": u.learning_goals,
                    "prior_knowledge": u.prior_knowledge,
                    "learning_style": u.learning_style,
                    "time_commitment": u.time_commitment,
                    "preferred_format": u.preferred_format,
                    "created_at": u.created_at.isoformat(),
                    "modified_at": u.modified_at.isoformat()
                })
                objects_to_update.append(u)

            # Telemetry
            logs = TelemetryLog.query.filter((TelemetryLog.sync_status == 'pending') | (TelemetryLog.sync_status is None)).limit(BATCH_SIZE * 2).all()
            for log_event in logs:
                payload["telemetry_events"].append({
                    "session_id": log_event.session_id,
                    "timestamp": log_event.timestamp.isoformat(),
                    "event_type": log_event.event_type,
                    "payload": log_event.payload,
                    "created_at": log_event.created_at.isoformat(),
                    "modified_at": log_event.modified_at.isoformat()
                })
                objects_to_update.append(log_event)

            # Feedback
            feedbacks = Feedback.query.filter((Feedback.sync_status == 'pending') | (Feedback.sync_status is None)).limit(BATCH_SIZE).all()
            for f in feedbacks:
                payload["feedback"].append({
                    "user_id": f.user_id,
                    "feedback_type": f.feedback_type,
                    "content_reference": f.content_reference,
                    "rating": f.rating or 0, # Ensure integer
                    "comment": f.comment,
                    "created_at": f.created_at.isoformat(),
                    "modified_at": f.modified_at.isoformat()
                })
                objects_to_update.append(f)

            # PlanRevision
            plans = PlanRevision.query.filter((PlanRevision.sync_status == 'pending') | (PlanRevision.sync_status is None)).limit(BATCH_SIZE).all()
            for pr in plans:
                payload["plan_revisions"].append({
                    "topic_id": pr.topic_id,
                    "user_id": pr.user_id,
                    "reason": pr.reason,
                    "old_plan_json": pr.old_plan_json,
                    "new_plan_json": pr.new_plan_json,
                    "created_at": pr.created_at.isoformat(),
                    "modified_at": pr.modified_at.isoformat()
                })
                objects_to_update.append(pr)
                # Ensure parent topic is added
                if pr.topic and pr.topic.id not in included_topic_ids:
                    add_topic_to_payload(pr.topic)

            # AIModelPerformance
            perfs = AIModelPerformance.query.filter((AIModelPerformance.sync_status == 'pending') | (AIModelPerformance.sync_status is None)).limit(BATCH_SIZE).all()
            for p in perfs:
                payload["ai_performances"].append({
                    "user_id": p.user_id,
                    "model_type": p.model_type,
                    "model_name": p.model_name,
                    "latency_ms": p.latency_ms,
                    "input_tokens": p.input_tokens,
                    "output_tokens": p.output_tokens,
                    "timestamp": p.timestamp.isoformat(),
                    "created_at": p.created_at.isoformat(),
                    "modified_at": p.modified_at.isoformat()
                })
                objects_to_update.append(p)

            # Check if we have anything to send
            total_items = sum(len(v) for k, v in payload.items() if isinstance(v, list))
            if total_items == 0:
                return

            logger.debug(f"Syncing {total_items} items to DCS...")

            # Send to DCS
            resp = requests.post(f"{self.base_url}/api/sync", json=payload, timeout=30)
            resp.raise_for_status()

            # Update status on success
            for obj in objects_to_update:
                obj.sync_status = 'synced'

            # Log success
            log_entry = SyncLog(
                installation_id=self.installation_id,
                status='success',
                details={'items_count': total_items}
            )
            db.session.add(log_entry)
            db.session.commit()
            logger.debug("Sync successful")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            db.session.rollback()
            try:
                log_entry = SyncLog(
                    installation_id=self.installation_id,
                    status='failed',
                    details={'error': str(e)}
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception:
                pass

class SyncManager:
    """Background manager that periodically syncs data with DCS."""

    def __init__(self, app):
        """Initialize sync manager with Flask app context."""
        self.app = app
        self.client = DCSClient()
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        """Start the background sync thread."""
        # Initial check/register (blocking or non-blocking? User said "As soon as app starts... check")
        # We'll do it in the thread to not block startup UI, BUT required for valid functionality.
        # Ideally, we block `run.py` to ensure registration?
        # The prompt says: "As soon as the app starts, it should check... If missing, register... If present, start normally."
        # This implies blocking logic in `create_app` or `run.py` is accepted or desired.

        # However, for the sync loop:
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        """Main sync loop that runs in background thread."""
        with self.app.app_context():
            # Ensure registration first thing in the thread if not done
            if not self.client.register_device():
                logger.error("Could not register device. Sync will be disabled.")
                return

            while not self.stop_event.is_set():
                try:
                    self.client.sync_data()
                except Exception as e:
                    logger.error(f"Error in sync loop: {e}")

                # Wait 1 minute
                time.sleep(60)
