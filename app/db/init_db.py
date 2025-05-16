import sqlite3
from pathlib import Path

def init_db():
    db_path = Path("qa_warehouse.db")
    schema_path = Path("app/db/schema.sql")

    if not schema_path.exists():
        raise FileNotFoundError("❌ schema.sql not found!")

    with sqlite3.connect(db_path) as conn:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        print("✅ Database initialized at:", db_path)

if __name__ == "__main__":
    init_db()
