import sqlite3
from pathlib import Path

def get_connection(db_file: str = "qa_warehouse.db"):
    db_path = Path(db_file)
    if not db_path.exists():
        raise FileNotFoundError("Database not initialized. Please run init_db.py first.")
    return sqlite3.connect(db_path)
