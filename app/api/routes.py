import datetime
import os
import random
import time

from flask import Blueprint, jsonify
from sqlalchemy import text
from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService
  

from app.agents.monitor_agent import MonitorAgent
from app.agents.nasa_agent import NasaIngestionService
from app.agents.open_weather_map_agent import WeatherService
from app.extensions import db

# Create the Blueprint
api = Blueprint('api', __name__)


@api.route('/')
def home():
    """Returns a simple status message confirming that the FireCommand AI server is running and operational."""
    return "FireCommand AI Server is Running (Modular Structure)!"


@api.route('/test-db')
def test_db():
    """Tests database connectivity by executing a version query through the SQLAlchemy ORM and returns the database version string or an error message if the connection fails."""
    try:
        # Execute a version check query using raw SQL through ORM
        result = db.session.execute(text('SELECT version()'))
        version = result.fetchone()[0]
        return f"Read Success! Version: {version}"
    except Exception as e:
        return f"Connection Failed: {e}"


@api.route('/test-nasa')
def test_nasa():
    """Tests the NASA fire ingestion service by fetching and saving fire data from the last 5 days, then returns the results as JSON including the count of new fires added."""
    # Create service instance
    service = NasaIngestionService()

    # Fetch and save fires from the last 5 days
    fires_data = service.fetch_and_save_fires(days_back=5)

    # Return the result to screen as JSON
    return jsonify({
        "data": fires_data
    })


@api.route('/test-owm')
def test_owm():
    """Tests the OpenWeatherMap service by updating weather data for fire event ID 1, returning success status if the event exists or an error if the update fails."""
    # Create weather service instance
    service = WeatherService()

    # Update weather data for event ID 1
    success = service.update_weather_for_event(1)

    # Return response to browser indicating success or failure
    if success:
        return jsonify({"status": "success", "message": "Weather updated for Event #1"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed. Does Event #1 exist in DB?"}), 400


@api.route('/run-monitor', methods=['GET'])
def run_monitor():
    """Executes a complete monitoring cycle including fire clustering and weather enrichment, then returns the execution status and total time taken in seconds."""
    start_time = time.time()
    try:
        # Create the monitor agent
        agent = MonitorAgent()

        # Run the monitoring cycle (clustering and weather enrichment)
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
    """Performs a complete system test by running NASA fire ingestion followed by the monitoring cycle, returning detailed results including fire counts and execution time."""
    start_time = time.time()
    results = {}

    try:
        # Run NASA ingestion first
        nasa_service = NasaIngestionService()
        fires_data = nasa_service.fetch_and_save_fires(days_back=5)
        results['nasa_ingestion'] = {
            "status": "success",
            "fires_count": fires_data.get("new_fires_added", 0)
        }

        # Run monitor cycle after NASA ingestion
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


from app.extensions import socketio


@api.route('/trigger-fire')
def trigger_fire():
    """Creates 5 simulated fire events with random coordinates around the Jerusalem area for load testing purposes, emitting each event via WebSocket and returning the generated data."""
    fires = []
    for i in range(5):
        # Generate random fire coordinates around Jerusalem
        fake_fire = {
            "event_id": 900 + i,
            "lat": 31.7 + random.uniform(-0.1, 0.1),
            "lon": 35.2 + random.uniform(-0.1, 0.1),
            "intensity": "High"
        }
        fires.append(fake_fire)
        # Emit each fire event via WebSocket
        socketio.emit('new_fire', fake_fire)

    return jsonify({"status": "5 Alerts sent!", "data": fires})


@api.route('/active-fires', methods=['GET'])
def get_active_fires():
    """Retrieves all active fire events from the database along with the most recent command log summaries for each affected district, returning fires and summaries as a combined JSON response."""
    try:
        from app.models.fire_events import FireEvent
        from app.models.commander_logs import CommandLog

        # Fetch all active fire events and convert them to dictionary
        active_fires = FireEvent.query.all()
        fires_list = [fire.to_dict() for fire in active_fires]

        # Extract unique districts from fire events
        active_districts = set(f.get('district') for f in fires_list if f.get('district'))

        # Fetch the most recent recommendation from command log for each active district
        summaries = {}
        for district in active_districts:
            latest_log = CommandLog.query.filter_by(district_name=district) \
                .order_by(CommandLog.timestamp.desc()) \
                .first()
            if latest_log:
                summaries[district] = latest_log.llm_summary_text

        # Return combined object
        return jsonify({
            "fires": fires_list,
            "summaries": summaries
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_full_system_sync():
    """Executes a complete system synchronization by running NASA fire ingestion followed by the monitor cycle, logging progress with process ID timestamps and returning results or error information."""
    current_pid = os.getpid()
    start_time = datetime.datetime.now()
    print(f"🔄 [PID {current_pid}] [SYNC START] {start_time.strftime('%H:%M:%S')} - Initializing full system update...")
    start_time = time.time()
    results = {}
    try:
        # Run NASA fire ingestion
        nasa_service = NasaIngestionService()
        fires_data = nasa_service.fetch_and_save_fires(days_back=5)
        results['nasa_ingestion'] = {
            "status": "success",
            "fires_count": fires_data.get("new_fires_added", 0)
        }

        # Run monitor cycle
        print(f"🛑 [PID {current_pid}] Running Monitor Cycle..")
        monitor_agent = MonitorAgent()
        monitor_agent.run_cycle()
        results['monitor_cycle'] = {"status": "success"}

        print(f"✅ [PID {current_pid}] Sync completed in {time.time() - start_time:.2f}s")
        return results
    except Exception as e:
        print(f"❌ [PID {current_pid}] Sync failed: {e}")
        return {"error": str(e)}


@socketio.on('connect')
def handle_connect():
    """Handles WebSocket connection events from React clients, logging the connection with the current process ID."""
    print(f"🟢 [PID {os.getpid()}] React Client just connected to me!")


@socketio.on('disconnect')
def handle_disconnect():
    """Handles WebSocket disconnection events when clients close the browser or disconnect, logging the disconnection with the current process ID."""
    print(f"🟡 [PID {os.getpid()}] React Client disconnected.")


from app.models.resources import Station


@api.route('/stations', methods=['GET'])
def get_stations():
    """Fetches all fire stations from the database and returns them in standard GeoJSON format with features containing point geometries and station properties for the React map."""
    stations = Station.query.all()

    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for station in stations:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                # GeoJSON coordinate order is always [longitude, latitude]
                "coordinates": [station.longitude, station.latitude]
            },
            "properties": {
                "id": station.id,
                "name": station.name,
                "district": station.district,
                "type": station.station_type
            }
        }
        geojson["features"].append(feature)

    return jsonify(geojson)


@api.route('/health', methods=['GET'])
def health_check():
    """Dedicated health check endpoint for UptimeRobot monitoring to keep the server awake, returning a simple alive status with the current timestamp logged."""
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"🩺 [{current_time}] [KEEP-ALIVE] UptimeRobot pinged /health")
    return {"status": "alive", "message": "FireCommand is awake!"}, 200



# ודא שיש לך את ה-import של cross_origin בראש הקובץ או כאן
from flask_cors import cross_origin

@api.route('/api/debug/reset', methods=['POST', 'OPTIONS']) # הוספנו תמיכה מפורשת ב-OPTIONS עבור ה-Preflight
@cross_origin() # מכריח את Flask לאשר CORS ספציפית לראוט הזה
def reset_database_route():
    try:
        print("🚨 [API Request] Received reset command from React Dashboard...")
        
        # הייבוא המקומי שפותר את ה-Circular Import
        from init_db import initialize_database  
        
        # הרצת הלוגיקה שלך
        initialize_database()
        
        print("✅ [API Request] Database successfully re-initialized.")
        return jsonify({
            "status": "success", 
            "message": "Database cleared and re-seeded successfully."
        }), 200
        
    except Exception as e:
        print(f"❌ [API Request] Reset failed with error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
