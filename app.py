import os
import psycopg2
from flask import Flask, jsonify

app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))


@app.route('/')
def home():
    return "FireCommand AI Server is Running!"


# בדיקת חיבור בסיסית (מה שעשינו קודם)
@app.route('/test-db')
def test_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT version();')
        db_version = cur.fetchone()
        cur.close()
        conn.close()
        return f"Read Success! Version: {db_version[0]}"
    except Exception as e:
        return f"Connection Failed: {e}"


# בדיקת כתיבה: יצירת טבלה והכנסת ערך
@app.route('/init-db')
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. יצירת טבלה פשוטה אם היא לא קיימת
        cur.execute("CREATE TABLE IF NOT EXISTS test_log (id SERIAL PRIMARY KEY, message TEXT);")

        # 2. הכנסת נתונים (INSERT)
        cur.execute("INSERT INTO test_log (message) VALUES ('Hello from Flask! Write check passed.');")

        # חובה לעשות commit כדי לשמור את השינויים!
        conn.commit()

        # 3. שליפה (SELECT) כדי לראות שזה באמת שם
        cur.execute("SELECT * FROM test_log;")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        # החזרת התוצאה כ-JSON
        return jsonify({
            "status": "success",
            "message": "Table created and row inserted!",
            "current_data": rows
        })

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


if __name__ == '__main__':
    app.run(debug=True, port=5000)