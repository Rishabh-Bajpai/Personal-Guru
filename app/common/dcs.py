import os
import requests
import json
import logging
import datetime
import threading
import time
from app.core.extensions import db
from app.core.models import Installation, Topic, ChatMode, ChapterMode, QuizMode, FlashcardMode, User, TelemetryLog, Feedback, AIModelPerformance, PlanRevision, SyncLog

logger = logging.getLogger(__name__)

DCS_BASE_URL = os.getenv("DCS_BASE_URL", "https://telemetry.samosa-ai.com")

class DCSClient:
    def __init__(self):
        self.base_url = DCS_BASE_URL
        self.installation_id = None
        self._load_installation_id()

    def _load_installation_id(self):
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
        
        # Check if already registered
        inst = Installation.query.first()
        if inst:
            self.installation_id = inst.installation_id
            logger.info(f"Device already registered with ID: {self.installation_id}")
            # Optionally update details
            self.update_device_details()
            return True

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

        # Start a new DB session context for the thread
        # In Flask, we need ap_context usually, handled by caller or here
        
        payload = {
            "installation_id": self.installation_id,
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
        
        # Helper to fetch pending records
        # Limit batch size to avoid huge payloads
        BATCH_SIZE = 50 
        
        objects_to_update = []
        
        try:
            # Topics
            topics = Topic.query.filter((Topic.sync_status == 'pending') | (Topic.sync_status == None)).limit(BATCH_SIZE).all()
            for t in topics:
                payload["topics"].append({
                    "id": t.id,
                    "user_id": t.user_id,
                    "name": t.name,
                    "study_plan": t.study_plan,
                    "created_at": t.created_at.isoformat(),
                    "modified_at": t.modified_at.isoformat()
                })
                objects_to_update.append(t)

            # ChatMode
            chats = ChatMode.query.filter((ChatMode.sync_status == 'pending') | (ChatMode.sync_status == None)).limit(BATCH_SIZE).all()
            for c in chats:
                payload["chat_modes"].append({
                    "topic_id": c.topic_id,
                    "user_id": c.user_id,
                    "history": c.history,
                    "time_spent": c.time_spent,
                    "created_at": c.created_at.isoformat(),
                    "modified_at": c.modified_at.isoformat()
                })
                objects_to_update.append(c)

            # ChapterMode
            chapters = ChapterMode.query.filter((ChapterMode.sync_status == 'pending') | (ChapterMode.sync_status == None)).limit(BATCH_SIZE).all()
            for c in chapters:
                payload["chapter_modes"].append({
                    "topic_id": c.topic_id,
                    "user_id": c.user_id,
                    "step_index": c.step_index,
                    "title": c.title,
                    "questions": c.questions,
                    "user_answers": c.user_answers,
                    "score": c.score,
                    "time_spent": c.time_spent,
                    "created_at": c.created_at.isoformat(),
                    "modified_at": c.modified_at.isoformat()
                })
                objects_to_update.append(c)

            # QuizMode
            quizzes = QuizMode.query.filter((QuizMode.sync_status == 'pending') | (QuizMode.sync_status == None)).limit(BATCH_SIZE).all()
            for q in quizzes:
                payload["quiz_modes"].append({
                    "topic_id": q.topic_id,
                    "user_id": q.user_id,
                    "score": q.score,
                    "result": q.result,
                    "time_spent": q.time_spent,
                    "created_at": q.created_at.isoformat(),
                    "modified_at": q.modified_at.isoformat()
                })
                objects_to_update.append(q)

            # FlashcardMode
            flashcards = FlashcardMode.query.filter((FlashcardMode.sync_status == 'pending') | (FlashcardMode.sync_status == None)).limit(BATCH_SIZE).all()
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

            # User Profile
            users = User.query.filter((User.sync_status == 'pending') | (User.sync_status == None)).limit(BATCH_SIZE).all()
            for u in users:
                payload["user_profiles"].append({
                    "login_id": u.login_id,
                    "age": u.age,
                    "country": u.country,
                    "learning_goals": u.learning_goals,
                    "created_at": u.created_at.isoformat(),
                    "modified_at": u.modified_at.isoformat()
                })
                objects_to_update.append(u)
                
            # Telemetry
            logs = TelemetryLog.query.filter((TelemetryLog.sync_status == 'pending') | (TelemetryLog.sync_status == None)).limit(BATCH_SIZE * 2).all()
            for l in logs:
                payload["telemetry_events"].append({
                    "session_id": l.session_id,
                    "timestamp": l.timestamp.isoformat(),
                    "event_type": l.event_type,
                    "payload": l.payload,
                    "created_at": l.created_at.isoformat(),
                    "modified_at": l.modified_at.isoformat()
                })
                objects_to_update.append(l)

            # Check if we have anything to send
            total_items = sum(len(v) for k, v in payload.items() if isinstance(v, list))
            if total_items == 0:
                return

            logger.info(f"Syncing {total_items} items to DCS...")
            
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
            logger.info("Sync successful")

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
            except:
                pass

class SyncManager:
    def __init__(self, app):
        self.app = app
        self.client = DCSClient()
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        # Initial check/register (blocking or non-blocking? User said "As soon as app starts... check")
        # We'll do it in the thread to not block startup UI, BUT required for valid functionality.
        # Ideally, we block `run.py` to ensure registration? 
        # The prompt says: "As soon as the app starts, it should check... If missing, register... If present, start normally."
        # This implies blocking logic in `create_app` or `run.py` is accepted or desired.
        
        # However, for the sync loop:
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
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

