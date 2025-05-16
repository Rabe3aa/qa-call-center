import json
import os
from datetime import datetime
from app.db.connection import get_connection

def already_exists(call_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM fact_call_evaluation WHERE call_id = ? LIMIT 1", (call_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def insert_report(report_path: str, company_id: str, call_id: str, agent_id: str = "unknown"):
    if not os.path.exists(report_path):
        raise FileNotFoundError(f"Report not found at: {report_path}")
    
    if already_exists(call_id):
        print(f"⚠️ Call ID {call_id} already exists — skipping.")
        return

    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)

    scores = data.get("scores", {})
    insert_rows = []

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    for criterion, score in scores.items():
        qa_score = None
        if score == "PASS":
            qa_score = 1
        elif score == "FAIL":
            qa_score = 0

        insert_rows.append((
            call_id, company_id, agent_id,
            criterion, score, qa_score,
            date, time
        ))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany("""
        INSERT INTO fact_call_evaluation (
            call_id, company_id, agent_id,
            criterion, score, qa_score,
            date, time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, insert_rows)

    conn.commit()
    conn.close()
    print(f"✅ Inserted {len(insert_rows)} scores for call {call_id} ({company_id})")

if __name__ == "__main__":
    # Example: test with a real path
    insert_report(
        report_path="reports/EDGE-CONTACT-CENTER/q-9000-0225173712-20240112-103101-1705048249.105523/report.json",
        company_id="EDGE-CONTACT-CENTER",
        call_id="q-9000-0225173712-20240112-103101-1705048249.105523"
    )
