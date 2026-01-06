from app.core.extensions import db
# from pgvector.sqlalchemy import Vector
import datetime
from sqlalchemy import JSON
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Topic(db.Model):
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('users.username'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='_user_topic_uc'),
    )
    
    # Relationships
    # Relationships
    study_plan = db.Column(JSON) # Storing list of strings as JSON
    steps = db.relationship('StudyStep', backref='topic', cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='topic', cascade='all, delete-orphan')
    flashcards = db.relationship('Flashcard', backref='topic', cascade='all, delete-orphan')
    chat_session = db.relationship('ChatSession', backref='topic', uselist=False, cascade='all, delete-orphan')

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False, unique=True)
    history = db.Column(JSON)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class StudyStep(db.Model):
    __tablename__ = 'study_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    step_index = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255))
    content = db.Column(db.Text) # Markdown content
    
    # Questions and Feedback stored as JSON
    questions = db.Column(JSON) 
    user_answers = db.Column(JSON)
    feedback = db.Column(JSON)
    score = db.Column(db.Float)
    chat_history = db.Column(JSON) # Store chat history for this step
    
class Quiz(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    questions = db.Column(JSON) # List of question objects
    score = db.Column(db.Float)
    result = db.Column(JSON) # Detailed result (last_quiz_result)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Flashcard(db.Model):
    __tablename__ = 'flashcards'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    term = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    username = db.Column(db.String(100), primary_key=True)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    country = db.Column(db.String(100))
    primary_language = db.Column(db.String(100))
    education_level = db.Column(db.String(100))
    field_of_study = db.Column(db.String(100))
    occupation = db.Column(db.String(100))
    learning_goals = db.Column(db.Text)
    prior_knowledge = db.Column(db.Text)
    learning_style = db.Column(db.String(100))
    time_commitment = db.Column(db.String(100))
    preferred_format = db.Column(db.String(100))
    installation_id = db.Column(db.String(36), db.ForeignKey('installations.installation_id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.username

    def to_context_string(self):
        """Generates a text description of the user profile for LLM context."""
        parts = []
        if self.name:
            parts.append(f"Name: {self.name}")
        if self.age:
            parts.append(f"Age: {self.age}")
        if self.country:
            parts.append(f"Country: {self.country}")
        if self.primary_language:
            parts.append(f"Primary Language: {self.primary_language}")
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

# class VectorEmbedding(db.Model):
#     __tablename__ = 'vector_embeddings'
#     
#     id = db.Column(db.Integer, primary_key=True)
#     content = db.Column(db.Text, nullable=False)
#     embedding = db.Column(Vector(1536)) # Assuming OpenAI Ada-002 dimension
#     metadata_json = db.Column(JSONB)

class Installation(db.Model):
    __tablename__ = 'installations'

    installation_id = db.Column(db.String(36), primary_key=True)  # UUID
    cpu_cores = db.Column(db.Integer)
    ram_gb = db.Column(db.Float)
    gpu_model = db.Column(db.String(255))
    os_version = db.Column(db.String(255))
    install_method = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    users = db.relationship('User', backref='installation', lazy=True)
    telemetry_logs = db.relationship('TelemetryLog', backref='installation', lazy=True)


class TelemetryLog(db.Model):
    __tablename__ = 'telemetry_logs'

    id = db.Column(db.Integer, primary_key=True)
    installation_id = db.Column(db.String(36), db.ForeignKey('installations.installation_id'), nullable=False)
    session_id = db.Column(db.String(36))  # UUID
    event_type = db.Column(db.String(100), nullable=False)
    payload = db.Column(JSON)  # Stores latency, error logs, quiz scores, etc.
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Feedback(db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('users.username'), nullable=False)
    feedback_type = db.Column(db.String(50), nullable=False)  # 'form', 'in_place'
    content_reference = db.Column(db.String(255))  # ID of the generated content
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class LLMPerformance(db.Model):
    __tablename__ = 'llm_performance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey('users.username'), nullable=False)
    feature = db.Column(db.String(100))
    model_name = db.Column(db.String(100))
    latency_ms = db.Column(db.Integer)
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class PlanRevision(db.Model):
    __tablename__ = 'plan_revisions'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    user_id = db.Column(db.String(100), db.ForeignKey('users.username'), nullable=False)
    reason = db.Column(db.Text)
    old_plan_json = db.Column(JSON)
    new_plan_json = db.Column(JSON)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
