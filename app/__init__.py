import os
from flask import Flask
from app.extensions import db, socketio
from app.api.routes import api
from flask_cors import CORS
from apscheduler.schedulers.gevent import GeventScheduler
from datetime import datetime
from datetime import timedelta

def create_app():
    app = Flask(__name__)

    # תיקון קטן לכתובת של Neon (הם נותנים postgres:// אבל SQLAlchemy רוצה postgresql://)
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # אתחול ה-DB
    CORS(app)
    db.init_app(app)
    socketio.init_app(app)

    # רישום ה-Routes
    app.register_blueprint(api)

    # יצירת טבלאות אוטומטית (אם לא קיימות)
    with app.app_context():
        from app.models.nasa_fire import FireIncident  # וודא שזה שם הקובץ הנכון
        from app.models.fire_events import FireEvent
        from app.models.resources import Station, Resource
        from app.models.commander_logs import CommandLog
        db.create_all()

        if Station.query.first() is None:
            print("Empty station database detected. Starting initial data seeding")
            from app.services.seed_resources import seed_real_israel_stations
            seed_real_israel_stations()

    # הגדרת הריצה האוטומטית
    scheduler = GeventScheduler()

    def job():
        with app.app_context():
            # קורא לפונקציה שהוצאנו בצעד הקודם
            from app.api.routes import run_full_system_sync
            print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Starting scheduled sync cycle...")
            run_full_system_sync()

    # מוסיף משימה שרצה כל 5 דקות
    scheduler.add_job(func=job, trigger="interval", minutes=5, next_run_time=datetime.now() + timedelta(seconds=15))
    scheduler.start()

    return app