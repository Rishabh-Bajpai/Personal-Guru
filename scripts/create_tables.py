#!/usr/bin/env python
"""
Create database tables in PostgreSQL for the Personal Guru application.
"""
import sys
import os
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

from app import create_app, db

def create_tables():
    app = create_app()
    with app.app_context():
        print("Creating tables in PostgreSQL...")
        db.create_all()
        print("✓ Tables created successfully!")

if __name__ == '__main__':
    create_tables()
