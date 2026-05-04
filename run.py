import gevent.monkey
gevent.monkey.patch_all()

import os
from apscheduler.schedulers.gevent import GeventScheduler
from datetime import datetime, timedelta

from dotenv import load_dotenv # <--- הוספה חדשה
import os
from app.extensions import socketio

load_dotenv()
from app import create_app
app = create_app()

# הגדרת ה-Scheduler כאן מבטיחה שהוא לא ישתכפל בתוך create_app
scheduler = GeventScheduler(job_defaults={'coalesce': True, 'max_instances': 1})

def scheduled_task():
    with app.app_context():
        from app.api.routes import run_full_system_sync
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Starting sync cycle...")
        run_full_system_sync()

# הוספת המשימה והתנעה
if not scheduler.get_job('main_sync_job'):
    scheduler.add_job(
        id='main_sync_job',
        func=scheduled_task,
        trigger="interval",
        minutes=5,
        next_run_time=datetime.now() + timedelta(seconds=60),
        misfire_grace_time=30
    )
    scheduler.start()
    print(f"🚀 [PID {os.getpid()}] Scheduler started successfully.")

if __name__ == '__main__':
    socketio.run(app, debug=False, port=5000)