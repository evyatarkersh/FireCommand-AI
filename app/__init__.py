import os
from flask import Flask
from app.extensions import db, socketio
from app.api.routes import api
from flask_cors import CORS
from apscheduler.schedulers.gevent import GeventScheduler
from datetime import datetime
from datetime import timedelta

scheduler = GeventScheduler(job_defaults={'coalesce': True, 'max_instances': 1})

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

        # --- לוגיקת סנכרון המערכת ---
        def sync_job():
            with app.app_context():
                from app.api.routes import run_full_system_sync
                # ההדפסה הזו תופיע עכשיו רק פעם אחת בכל סבב
                print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Starting sync cycle...")
                run_full_system_sync()

        # 2. הפתרון לכפילות: הוספת המשימה עם ID קבוע ובדיקת קיום
        if not scheduler.get_job('main_sync_job'):
            scheduler.add_job(
                id='main_sync_job',  # תעודת הזהות של המשימה
                func=sync_job,
                trigger="interval",
                minutes=5,
                # ירוץ דקה אחרי הסטארט-אפ כדי שהפורט ייפתח בנחת
                next_run_time=datetime.now() + timedelta(seconds=60),
                misfire_grace_time=30,
                replace_existing=True
            )

        # 3. התנעת המנוע רק אם הוא לא פועל כבר
        if not scheduler.running:
            scheduler.start()
            print(f"🚀 [PID {os.getpid()}] Background Engine started.")

    return app