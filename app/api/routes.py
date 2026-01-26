from flask import Blueprint, jsonify
from app.extensions import db
from app.models.test_model import TestLog
from sqlalchemy import text
from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService

from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService
from app.agents.IMS_DATA_agent import fetch_weather_by_location
from app.agents.topo_agent import fetch_and_save_topography
from app.agents.monitor_agent import MonitorAgent

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

@api.route('/test-nasa')
def test_nasa():
    # 1. יצירת המופע של הסרביס
    service = NasaIngestionService()

    # 2. קריאה לפונקציה
    fires_data = service.fetch_and_save_fires(days_back=5)

    # 3. החזרת התוצאה למסך כ-JSON
    return jsonify({
        "data": fires_data
    })
@api.route('/test-owm')
def test_owm():
    # 1. יצירת המופע של הסרביס
    service = WeatherService()

    # 2. קריאה לפונקציה
    success = service.update_weather_for_event(1)

    # 3. החזרת תשובה לדפדפן כדי שנדע מה קרה
    if success:
        return jsonify({"status": "success", "message": "Weather updated for Event #1"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed. Does Event #1 exist in DB?"}), 400
    
    
# --- 🔥 הבדיקה החדשה: אינטגרציה מלאה (IMS + Topo) ---
@api.route('/test-agents')
def test_agents_integration():
    """
    בדיקה שמריצה את כל המעגל:
    יצירת שריפה -> IMS -> Topo -> הצגת התוצאה
    """
    try:
        # 1. יצירת שריפה פיקטיבית בכרמל (באמצעות SQL ישיר כי אין לנו עדיין מודל SQLAlchemy לזה)
        # אנחנו משתמשים ב-db.session כדי ליהנות מהחיבור הקיים של Flask
        lat, lon = 32.79, 35.01
        
        insert_query = text("""
            INSERT INTO fire_events (latitude, longitude, status) 
            VALUES (:lat, :lon, 'RENDER_TEST') 
            RETURNING id
        """)
        
        result = db.session.execute(insert_query, {'lat': lat, 'lon': lon})
        db.session.commit() # חובה כדי שהסוכנים יוכלו לראות את ה-ID הזה
        fire_id = result.fetchone()[0]
        
        print(f"🔥 Created test fire ID: {fire_id}")

        # 2. הפעלת סוכן IMS (מזג אוויר ישראלי)
        # הסוכנים שלנו עובדים עם psycopg2 עצמאי, זה בסדר גמור
        fetch_weather_by_location(lat, lon, fire_id)
        
        # 3. הפעלת סוכן טופוגרפיה
        fetch_and_save_topography(lat, lon, fire_id)

        # 4. שליפת התוצאה המלאה לבדיקה
        select_query = text("SELECT * FROM fire_events WHERE id = :id")
        row_result = db.session.execute(select_query, {'id': fire_id})
        
        # המרה ידנית של השורה למילון (כי זה Raw SQL)
        row = row_result.fetchone()
        columns = row_result.keys()
        data_dict = dict(zip(columns, row))

        return jsonify({
            "status": "success",
            "message": "Full integration cycle complete",
            "fire_data": data_dict
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Integration test failed",
            "details": str(e)
        }), 500


@api.route('/run-monitor', methods=['GET'])
def run_monitor():
    try:
        # 1. יצירת הסוכן
        agent = MonitorAgent()

        # 2. הרצת המחזור (Clustering + Weather Enrichment)
        agent.run_cycle()

        return jsonify({
            "status": "success",
            "message": "Monitor cycle finished successfully."
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500