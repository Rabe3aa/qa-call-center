import os
import json
from pathlib import Path
from app.db.etl_insert_report import insert_report
from app.db.connection import get_connection

def already_exists(call_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM fact_call_evaluation WHERE call_id = ? LIMIT 1", (call_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def scan_and_insert_reports(base_dir: str = "reports"):
    count = 0
    base = Path(base_dir)

    for company_dir in base.iterdir():
        if not company_dir.is_dir():
            continue

        for call_dir in company_dir.iterdir():
            report_path = call_dir / "report.json"
            call_id = call_dir.name
            company_id = company_dir.name

            if not report_path.exists():
                continue

            if already_exists(call_id):
                print(f"🟡 Skipping already inserted: {call_id}")
                continue

            print(f"🟢 Inserting new report: {call_id}")
            insert_report(
                report_path=str(report_path),
                company_id=company_id,
                call_id=call_id
            )
            count += 1

    print(f"\n✅ Completed scan — inserted {count} new reports.")

if __name__ == "__main__":
    scan_and_insert_reports()
