from flask import Blueprint, jsonify
from app.extensions import db
from app.models.test_model import TestLog
from sqlalchemy import text
from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService

# --- ייבוא הסוכנים החדשים ---
from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService
from app.agents.monitor_agent import MonitorAgent
from app.agents.topo_agent import enrich_with_topography
from app.agents.fuel_agent import enrich_with_fuel
from app.agents.IMS_DATA_agent import enrich_with_ims
import time, random

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
    
    


@api.route('/run-monitor', methods=['GET'])
def run_monitor():
    start_time = time.time()
    try:
        # 1. יצירת הסוכן
        agent = MonitorAgent()

        # 2. הרצת המחזור (Clustering + Weather Enrichment)
        agent.run_cycle()

        total_time = time.time() - start_time
        print(f"Total time: {total_time}")
        return jsonify({
            "status": "success",
            "message": "Monitor cycle finished successfully.",
            "total_time_seconds": total_time
        }), 200

    except Exception as e:
        total_time = time.time() - start_time
        print(f"Total time: {total_time}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@api.route('/test-all', methods=['GET'])
def ingest_and_monitor():
    start_time = time.time()
    results = {}

    try:
        # 1. Run NASA ingestion first
        nasa_service = NasaIngestionService()
        fires_data = nasa_service.fetch_and_save_fires(days_back=5)
        results['nasa_ingestion'] = {
            "status": "success",
            "fires_count": fires_data.get("new_fires_added", 0)
        }

        # 2. Run monitor cycle after NASA ingestion
        monitor_agent = MonitorAgent()
        monitor_agent.run_cycle()
        results['monitor_cycle'] = {
            "status": "success"
        }

        total_time = time.time() - start_time
        return jsonify({
            "status": "success",
            "message": "NASA ingestion and monitor cycle completed successfully.",
            "results": results,
            "total_time_seconds": total_time
        }), 200

    except Exception as e:
        total_time = time.time() - start_time
        return jsonify({
            "status": "error",
            "message": str(e),
            "results": results,
            "total_time_seconds": total_time
        }), 500


from app.extensions import socketio # ייבוא בתחילת הקובץ

@api.route('/trigger-fire')
def trigger_fire():
    # פונקציה לבדיקת עומס - יוצרת 5 שריפות אקראיות באזור ירושלים
    fires = []
    for i in range(5):
        fake_fire = {
            "event_id": 900 + i,
            "lat": 31.7 + random.uniform(-0.1, 0.1), # הגרלה סביב ירושלים
            "lon": 35.2 + random.uniform(-0.1, 0.1),
            "intensity": "High"
        }
        fires.append(fake_fire)
        socketio.emit('new_fire', fake_fire) # משדר כל אחת

    return jsonify({"status": "5 Alerts sent!", "data": fires})

@api.route('/active-fires', methods=['GET'])
def get_active_fires():
    try:
        # שליפת כל אירועי השריפה הפעילים מה-DB
        # (השתמשתי ב-FireEvent, וודא שזה השם הנכון אצלך)
        from app.models.fire_events import FireEvent
        active_fires = FireEvent.query.all()
        
        # המרה של רשימת האובייקטים למילונים פשוטים שה-React יבין
        return jsonify([fire.to_dict() for fire in active_fires]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_full_system_sync():
    """הלוגיקה שאתה כבר כתבת, בתוך פונקציה שאפשר לקרוא לה מכל מקום"""
    start_time = time.time()
    results = {}
    try:
        # 1. NASA Ingestion
        nasa_service = NasaIngestionService()
        fires_data = nasa_service.fetch_and_save_fires(days_back=5)
        results['nasa_ingestion'] = {
            "status": "success",
            "fires_count": fires_data.get("new_fires_added", 0)
        }

        # 2. Monitor Cycle
        monitor_agent = MonitorAgent()
        monitor_agent.run_cycle()
        results['monitor_cycle'] = {"status": "success"}

        print(f"✅ Sync completed in {time.time() - start_time:.2f}s")
        return results
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        return {"error": str(e)}