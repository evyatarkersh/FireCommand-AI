from flask import Blueprint, jsonify
from sqlalchemy import text
from app.extensions import db
from app.models.test_model import TestLog
from app.models.fire_events import FireEvent

# --- ייבוא הסוכנים החדשים ---
from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService
from app.agents.monitor_agent import MonitorAgent
from app.agents.topo_agent import enrich_with_topography
from app.agents.fuel_agent import enrich_with_fuel
from app.agents.IMS_DATA_agent import enrich_with_ims

# יצירת ה-Blueprint
api = Blueprint('api', __name__)

@api.route('/')
def home():
    return "FireCommand AI Server is Running (Optimized Architecture)!"

# --- בדיקות בסיסיות ל-DB ---

@api.route('/test-db')
def test_db():
    try:
        result = db.session.execute(text('SELECT version()'))
        version = result.fetchone()[0]
        return f"Read Success! Version: {version}"
    except Exception as e:
        return f"Connection Failed: {e}"

@api.route('/init-db')
def init_db():
    try:
        new_log = TestLog(message='Hello from Optimized Flask!')
        db.session.add(new_log)
        db.session.commit()
        all_logs = TestLog.query.all()
        return jsonify({
            "status": "success",
            "message": "Row inserted via ORM!",
            "current_data": [log.to_dict() for log in all_logs]
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

# --- בדיקות סוכנים ---

@api.route('/test-nasa')
def test_nasa():
    service = NasaIngestionService()
    fires_data = service.fetch_and_save_fires(days_back=1) # הורדתי ל-1 יום כדי שיהיה מהיר
    return jsonify({"data": fires_data})

@api.route('/test-owm')
def test_owm():
    """
    בדיקת סוכן מזג אוויר על אובייקט זמני (ללא שמירה ל-DB)
    """
    try:
        # יצירת אובייקט דמי בזיכרון
        mock_event = FireEvent(id=999, latitude=32.08, longitude=34.78) # תל אביב
        
        service = WeatherService()
        success = service.update_weather_for_event(mock_event)

        if success:
            return jsonify({
                "status": "success", 
                "temp": mock_event.owm_temperature,
                "wind": mock_event.owm_wind_speed
            }), 200
        else:
            return jsonify({"status": "error", "message": "Weather Agent Failed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api.route('/test-agents')
def test_agents_integration():
    """
    🔥 הבדיקה המלאה: מריצה את כל הסוכנים החדשים על אירוע אחד.
    """
    try:
        # 1. יצירת שריפה לבדיקה (בכרמל)
        test_event = FireEvent(
            latitude=32.74, 
            longitude=35.04, 
            detected_at=db.func.now(),
            source="MANUAL_TEST"
        )
        
        # הוספה ל-Session (כדי שיהיה מנוהל), אבל עדיין לא Commit
        db.session.add(test_event)
        
        print("🚀 Starting Integration Test...")

        # 2. הרצת הסוכנים החדשים (שמקבלים אובייקט)
        enrich_with_topography(test_event)
        enrich_with_fuel(test_event)
        enrich_with_ims(test_event)
        
        # סוכן מזג אוויר הוא Class, אז צריך ליצור מופע
        ws = WeatherService()
        ws.update_weather_for_event(test_event)

        # 3. שמירה ל-DB (כדי לוודא שהכל תקין ברמת הטבלה)
        db.session.commit()
        
        print(f"✅ Test Event Saved! ID: {test_event.id}")

        # 4. החזרת הנתונים שהתקבלו
        return jsonify({
            "status": "success",
            "message": "All agents ran successfully",
            "data": {
                "id": test_event.id,
                "lat": test_event.latitude,
                "lon": test_event.longitude,
                "fuel": {"type": test_event.fuel_type, "load": test_event.fuel_load},
                "topo": {"elev": test_event.topo_elevation, "slope": test_event.topo_slope},
                "ims": {"temp": test_event.ims_temp, "station": test_event.ims_station_id},
                "owm": {"temp": test_event.owm_temperature, "wind": test_event.owm_wind_speed}
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error", 
            "message": "Integration test failed", 
            "details": str(e)
        }), 500

@api.route('/run-monitor', methods=['GET'])
def run_monitor():
    """
    מפעיל את המוניטור המלא (הלולאה הראשית)
    """
    try:
        agent = MonitorAgent()
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