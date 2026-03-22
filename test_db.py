import os

from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5433/personal_guru"
)

print("Connecting...")
try:
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    print("Success")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")
