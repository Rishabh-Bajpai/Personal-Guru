
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

from app import create_app, db  # noqa: E402
from sqlalchemy import text  # noqa: E402

def clear_database():
    """
    Drops all tables from the database and recreates them.
    This will delete all data.
    """
    print("WARNING: This will delete all data from the database.")
    confirm1 = input("Are you sure you want to continue? (yes/no): ")
    if confirm1.lower() != 'yes':
        print("Aborting.")
        return

    print("This is your final warning. This action cannot be undone.")
    confirm2 = input("Type 'delete all data' to confirm: ")
    if confirm2 != 'delete all data':
        print("Aborting.")
        return

    print("Clearing the database...")
    app = create_app()
    with app.app_context():
        table_names = db.metadata.tables.keys()
        db.session.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE;"))
        db.session.commit()
    print("Database cleared successfully.")

if __name__ == "__main__":
    clear_database()
