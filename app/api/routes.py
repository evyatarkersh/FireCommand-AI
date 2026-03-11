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
import time

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
