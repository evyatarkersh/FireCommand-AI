from flask import Blueprint, jsonify
from app.extensions import db
from app.models.test_model import TestLog
from sqlalchemy import text

# יצירת ה-Blueprint
api = Blueprint('api', __name__)


@api.route('/')
def home():
    return "FireCommand AI Server is Running (Modular Structure)!"


# בדיקת קריאה (במקום SQL, משתמשים ב-db.session)
@api.route('/test-db')
def test_db():
    try:
        # בדיקת גרסה מהירה באמצעות SQL נקי דרך ה-ORM
        result = db.session.execute(text('SELECT version()'))
        version = result.fetchone()[0]
        return f"Read Success! Version: {version}"
    except Exception as e:
        return f"Connection Failed: {e}"


# בדיקת כתיבה (במקום INSERT ידני, יוצרים אובייקט)
@api.route('/init-db')
def init_db():
    try:
        # 1. הוספת שורה חדשה
        new_log = TestLog(message='Hello from Flask Modular Structure!')
        db.session.add(new_log)
        db.session.commit()

        # 2. שליפת כל השורות
        all_logs = TestLog.query.all()

        # המרה ל-JSON
        return jsonify({
            "status": "success",
            "message": "Row inserted via ORM!",
            "current_data": [log.to_dict() for log in all_logs]
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})