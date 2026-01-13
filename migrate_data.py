import os
import json
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db  # noqa: E402
from app.common import storage  # noqa: E402


def migrate():
    """
    Migrate data from JSON files to PostgreSQL.
    """
    app = create_app()
    with app.app_context():
        # Create all tables first
        db.create_all()
        print("Database tables created.")

        data_dir = "data"
        if not os.path.exists(data_dir):
            print("No data directory found.")
            return

        files = [f for f in os.listdir(data_dir) if f.endswith(".json")]
        print(f"Found {len(files)} JSON files to migrate.")

        for filename in files:
            topic_name = filename.replace(".json", "")
            filepath = os.path.join(data_dir, filename)

            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                print(f"Migrating topic: {topic_name}")
                storage.save_topic(topic_name, data)

            except Exception as e:
                print(f"Failed to migrate {filename}: {e}")

        print("Migration complete.")


if __name__ == "__main__":
    migrate()
