#!/usr/bin/env python
"""
Update database schema in PostgreSQL for the Personal Guru application.
Handles creating missing tables and adding missing columns/updating column types.
"""
import sys
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import inspect, text

# Output buffer for detailed logs (to prevent spamming stdout if not needed, but here we print)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

from app import create_app, db
from app.common import models

# List of models to check
TARGET_MODELS = [
    models.Topic,
    models.StudyStep,
    models.Quiz,
    models.Flashcard
]

def get_column_type(column):
    """
    Returns a string representation of the column type for comparison.
    Simplified for common types used in this app.
    """
    return str(column.type).upper()

def update_database():
    app = create_app()
    with app.app_context():
        logger.info("Starting database update...")
        inspector = inspect(db.engine)
        
        # 1. Create missing tables (Standard SQLAlchemy)
        logger.info("Ensuring all tables exist...")
        db.create_all()
        
        # 2. Inspect and Update existing tables
        logger.info("Checking for schema updates...")
        
        for model in TARGET_MODELS:
            table_name = model.__tablename__
            logger.info(f"Inspecting table: {table_name}")
            
            # Get existing columns in DB
            existing_columns = inspector.get_columns(table_name)
            existing_col_map = {col['name']: col for col in existing_columns}
            
            # Get model columns
            model_columns = model.__table__.columns
            
            for column in model_columns:
                col_name = column.name
                col_type = column.type
                
                # Check if column exists
                if col_name not in existing_col_map:
                    logger.info(f"  [+] Adding missing column: {col_name} ({col_type})")
                    # Construct ALTER TABLE statement
                    # Note: This is basic. Default values and nullability might need more complex handling.
                    # For now, we add the column. If not nullable without default, Postgres will complain if table not empty.
                    # We assume nullable or we let it fail if strict.
                    try:
                        # Compile type to SQL string
                        type_str = col_type.compile(dialect=db.engine.dialect)
                        sql = text(f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {type_str}')
                        db.session.execute(sql)
                        db.session.commit()
                        logger.info("      -> Added successfully.")
                    except Exception as e:
                        logger.error(f"      -> FAILED to add column: {e}")
                        db.session.rollback()
                        
                else:
                    # Column exists, check for specific type updates requested (JSONB -> JSON)
                    existing_col_info = existing_col_map[col_name]
                    existing_type_str = str(existing_col_info['type']).upper()
                    model_type_str = str(col_type).upper()
                    
                    # Specific check for JSONB -> JSON
                    # Postgres generic JSON is often represented as 'JSON'
                    # Postgres JSONB is 'JSONB'
                    
                    if 'JSON' in model_type_str and 'JSONB' in existing_type_str:
                         logger.info(f"  [~] Converting column {col_name} from JSONB to JSON")
                         try:
                             # Cast using ::json
                             sql = text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{col_name}" TYPE JSON USING "{col_name}"::json')
                             db.session.execute(sql)
                             db.session.commit()
                             logger.info("      -> Converted successfully.")
                         except Exception as e:
                             logger.error(f"      -> FAILED to convert column: {e}")
                             db.session.rollback()
                    
                    # You can add more type checks here if needed
                    
        logger.info("✓ Database update complete!")

if __name__ == '__main__':
    update_database()
