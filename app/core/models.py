from app.core.extensions import db
# from pgvector.sqlalchemy import Vector
import datetime
from sqlalchemy import JSON
from werkzeug.security import generate_password_hash, check_password_hash

# UserMixin provides default implementations for the methods that Flask-Login expects user objects to have:
# is_authenticated, is_active, is_anonymous, and get_id.
from flask_login import UserMixin 

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    modified_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

class Topic(TimestampMixin, db.Model):
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('logins.userid'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    study_plan = db.Column(JSON) # Storing list of strings as JSON
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='_user_topic_uc'),
    )
    
    # Relationships
    steps = db.relationship('ChapterMode', backref='topics', cascade='all, delete-orphan')
    quizzes = db.relationship('QuizMode', backref='topics', uselist=False, cascade='all, delete-orphan')
    flashcards = db.relationship('FlashcardMode', backref='topics', cascade='all, delete-orphan')
    chat_mode = db.relationship('ChatMode', backref='topics', uselist=False, cascade='all, delete-orphan')
    plan_revisions = db.relationship('PlanRevision', backref='topics', uselist=False, cascade='all, delete-orphan')

class ChatMode(TimestampMixin, db.Model):
    __tablename__ = 'chat_mode'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topics.id'),
        nullable=False,
        unique=True)
    history = db.Column(JSON)
    time_spent = db.Column(db.Integer, default=0) # Duration in seconds

class ChapterMode(TimestampMixin, db.Model):
    __tablename__ = 'chapter_mode'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topics.id'),
        nullable=False)
    step_index = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255))
    content = db.Column(db.Text) # Markdown content
    podcast_audio_path = db.Column(db.String(512)) # path e.g. "/data/audio/podcast_<user_id><topic><step_id>.mp3"
    
    # Questions and Feedback stored as JSON
    questions = db.Column(JSON)
    user_answers = db.Column(JSON)
    user_answers = db.Column(JSON)
    score = db.Column(db.Float)
    chat_history = db.Column(JSON) # Store chat history for this step
    time_spent = db.Column(db.Integer, default=0) # Duration in seconds
    
class QuizMode(TimestampMixin, db.Model):
    __tablename__ = 'quiz_mode'
    
    id = db.Column(db.Integer, primary_key=True)
    # TODO: Remove unique constraint to allow multiple quizzes per topic
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False, unique=True)
    questions = db.Column(JSON, nullable=False) # List of question objects
    score = db.Column(db.Float)
    result = db.Column(JSON) # Detailed result (last_quiz_result)
    time_spent = db.Column(db.Integer, default=0) # Duration in seconds


class FlashcardMode(TimestampMixin, db.Model):
    __tablename__ = 'flashcard_mode'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('topics.id'),
        nullable=False)
    term = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    time_spent = db.Column(db.Integer, default=0) # Duration in seconds


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.String(100), db.ForeignKey('logins.userid'))
    age = db.Column(db.Integer)
    country = db.Column(db.String(100))
    languages = db.Column(JSON) # Storing list of strings as JSON
    education_level = db.Column(db.String(100))
    field_of_study = db.Column(db.String(100))
    occupation = db.Column(db.String(100))
    learning_goals = db.Column(db.Text)
    prior_knowledge = db.Column(db.Text)
    learning_style = db.Column(db.String(100))
    time_commitment = db.Column(db.String(100))
    preferred_format = db.Column(db.String(100))

    #Relationship
    login = db.relationship('Login', back_populates='user_profile', uselist=False)

    def to_context_string(self):
        """Generates a text description of the user profile for LLM context."""
        parts = []
        if self.login and self.login.name: 
            parts.append(f"Name: {self.login.name}")
        if self.age:
            parts.append(f"Age: {self.age}")
        if self.country:
            parts.append(f"Country: {self.country}")
        if self.languages:
            # Handle both string (legacy) and list (new)
            langs = self.languages
            if isinstance(langs, list):
                langs = ", ".join(langs)
            parts.append(f"Languages: {langs}")
        if self.education_level:
            parts.append(f"Education Level: {self.education_level}")
        if self.field_of_study:
            parts.append(f"Field of Study: {self.field_of_study}")
        if self.occupation:
            parts.append(f"Occupation: {self.occupation}")

        if self.learning_goals:
            parts.append(f"Learning Goals: {self.learning_goals}")
        if self.prior_knowledge:
            parts.append(f"Prior Knowledge: {self.prior_knowledge}")

        if self.learning_style:
            parts.append(f"Learning Style: {self.learning_style}")
        if self.time_commitment:
            parts.append(f"Time Commitment: {self.time_commitment}")
        if self.preferred_format:
            parts.append(f"Preferred Format: {self.preferred_format}")

        return "\n".join(parts)

class Installation(TimestampMixin, db.Model):
    __tablename__ = 'installations'

    installation_id = db.Column(db.String(36), primary_key=True)  # UUID
    cpu_cores = db.Column(db.Integer)
    ram_gb = db.Column(db.Integer)
    gpu_model = db.Column(db.String(255))
    os_version = db.Column(db.String(255))
    install_method = db.Column(db.String(100), nullable=False)  # 'docker', 'local', 'cloud'

    # Relationships
    logins = db.relationship('Login', backref='installations', cascade='all, delete-orphan')

# TODO: both id and session_id should be kept. session_id should come from Flask and id MUST be unique.
class TelemetryLog(TimestampMixin, db.Model):
    __tablename__ = 'telemetry_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('logins.userid'), nullable=False)
    session_id = db.Column(db.String(36), nullable=False)  # UUID
    event_type = db.Column(db.String(100), nullable=False) # TODO: event_tags like 'content_generated', 'quiz_completed', etc.
    triggers = db.Column(JSON, nullable=False) # event triggers like 'user_action', 'auto_save', etc.
    payload = db.Column(JSON, nullable=False)  # TODO: Define content structure. Stores latency, error logs, quiz scores, etc.
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)


class Feedback(TimestampMixin, db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('logins.userid'), nullable=False)
    feedback_type = db.Column(db.String(50), nullable=False)  # 'form', 'in_place'
    content_reference = db.Column(db.String(255))  # TODO: Define content tag like 'chapter_1', 'quiz_2', etc. Use topic_id, step_index etc. to uniquely identify content
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)


class AIModelPerformance(TimestampMixin, db.Model):
    __tablename__ = 'ai_model_performance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('logins.userid'), nullable=False)
    model_type = db.Column(db.String(100), nullable=False)  # 'LLM', 'Embedding', etc.
    model_name = db.Column(db.String(100))
    latency_ms = db.Column(db.Integer)
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class PlanRevision(TimestampMixin, db.Model):
    __tablename__ = 'plan_revisions'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    user_id = db.Column(db.String(100), db.ForeignKey('logins.userid'), nullable=False)
    reason = db.Column(db.Text) # Reason for revision, e.g., "User requested more advanced topics"
    old_plan_json = db.Column(JSON)
    new_plan_json = db.Column(JSON)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Login(UserMixin, TimestampMixin, db.Model):
    __tablename__ = 'logins'

    userid = db.Column(db.String(100), primary_key=True) 
    username = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100))
    password = db.Column(db.String(255))
    installation_id = db.Column(db.String(36), db.ForeignKey('installations.installation_id'))

    @staticmethod
    def generate_userid(installation_id=None):
        import uuid
        base_id = str(uuid.uuid4())
        if installation_id:
            return f"{base_id}_{installation_id}"
        return base_id

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def get_id(self):
        return self.userid

    # Relationships
    topics = db.relationship('Topic', backref='logins', cascade='all, delete-orphan')
    feedbacks = db.relationship('Feedback', backref='logins', cascade='all, delete-orphan')
    telemetry_logs = db.relationship('TelemetryLog', backref='logins', cascade='all, delete-orphan')
    llm_performances = db.relationship('AIModelPerformance', backref='logins', cascade='all, delete-orphan')
    plan_revisions = db.relationship('PlanRevision', backref='logins', cascade='all, delete-orphan')
    user_profile = db.relationship('User', back_populates='login', uselist=False)
