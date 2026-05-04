import gevent.monkey
gevent.monkey.patch_all()

import os
from apscheduler.schedulers.gevent import GeventScheduler
from datetime import datetime, timedelta

from dotenv import load_dotenv # <--- הוספה חדשה
import os
from app.extensions import socketio

# ניסיון ייבוא fcntl לנעילה ב-Linux (Render)
try:
    import fcntl
except ImportError:
    fcntl = None

load_dotenv()
from app import create_app
app = create_app()

scheduler = GeventScheduler(job_defaults={'coalesce': True, 'max_instances': 1})

def scheduled_task():
    with app.app_context():
        from app.api.routes import run_full_system_sync
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Starting sync cycle...")
        run_full_system_sync()

def start_scheduler():
    # אם אנחנו ב-Windows (לוקאלי), פשוט תתניע
    if fcntl is None:
        if not scheduler.get_job('main_sync_job'):
            scheduler.add_job(id='main_sync_job', func=scheduled_task, trigger="interval", minutes=5,
                             next_run_time=datetime.now() + timedelta(seconds=60), misfire_grace_time=30)
            scheduler.start()
            print(f"🚀 [LOCAL] Scheduler started successfully.")
        return

    # אם אנחנו ב-Render (Linux), חייבים נעילה כדי למנוע כפילות בגלל Gunicorn Fork
    f = open(".scheduler.lock", "wb")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not scheduler.get_job('main_sync_job'):
            scheduler.add_job(id='main_sync_job', func=scheduled_task, trigger="interval", minutes=5,
                             next_run_time=datetime.now() + timedelta(seconds=60), misfire_grace_time=30)
            scheduler.start()
            print(f"🚀 [RENDER PID {os.getpid()}] Scheduler Lock Acquired.")
    except (IOError, OSError):
        # אם התהליך כבר נעול, אנחנו פשוט לא מפעילים scheduler נוסף
        pass

# הפעלת הפונקציה החכמה
start_scheduler()

if __name__ == '__main__':
    socketio.run(app, debug=False, port=5000)