import os

import psycopg2
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "FireCommand AI Server is Running!"


@app.route('/test-db')
def test_db():
    try:
        # שליפת כתובת החיבור ממשתני הסביבה (שהגדרנו ב-Render)
        db_url = os.environ.get('DATABASE_URL')

        if not db_url:
            return "Error: DATABASE_URL environment variable is not set."

        # יצירת חיבור לדאטה-בייס
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # הרצת שאילתה פשוטה לבדיקת הגרסה
        cur.execute('SELECT version();')
        db_version = cur.fetchone()

        # סגירת החיבור
        cur.close()
        conn.close()

        return f"Success! Database Connected. Version: {db_version[0]}"
    except Exception as e:
        return f"Connection Failed: {e}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)