from app.db.connection import get_connection

def print_all_evaluations():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT call_id, company_id, criterion, score, qa_score, date, time
        FROM fact_call_evaluation
        ORDER BY date DESC, time DESC
        LIMIT 20
    """)

    rows = cursor.fetchall()
    for row in rows:
        print(row)

    conn.close()

if __name__ == "__main__":
    print_all_evaluations()
