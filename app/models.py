from app.extensions import db
from pgvector.sqlalchemy import Vector
import datetime
from sqlalchemy.dialects.postgresql import JSONB

class Topic(db.Model):
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    study_plan = db.Column(JSONB) # Storing list of strings as JSON
    steps = db.relationship('StudyStep', backref='topic', cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='topic', cascade='all, delete-orphan')
    flashcards = db.relationship('Flashcard', backref='topic', cascade='all, delete-orphan')

class StudyStep(db.Model):
    __tablename__ = 'study_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    step_index = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255))
    content = db.Column(db.Text) # Markdown content
    
    # Questions and Feedback stored as JSON
    questions = db.Column(JSONB) 
    user_answers = db.Column(JSONB)
    feedback = db.Column(JSONB)
    score = db.Column(db.Float)
    
class Quiz(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    questions = db.Column(JSONB) # List of question objects
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Flashcard(db.Model):
    __tablename__ = 'flashcards'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    term = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    
class VectorEmbedding(db.Model):
    __tablename__ = 'vector_embeddings'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(Vector(1536)) # Assuming OpenAI Ada-002 dimension
    metadata_json = db.Column(JSONB)
