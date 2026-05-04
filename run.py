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
    # מחכים 5 שניות כדי לוודא ש-Gunicorn סיים את ה-Fork-ים שלו
    # ושה-Master לא יפעיל את זה בעצמו
    gevent.sleep(5)

    if fcntl is None:  # Windows/Local
        init_actual_scheduler()
        return

    # ב-Render/Linux
    f = open(".scheduler.lock", "wb")
    try:
        # הנעילה תתבצע רק ב-Worker שיצליח לתפוס אותה ראשון אחרי ה-Delay
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        init_actual_scheduler()
        print(f"🚀 [FINAL PID {os.getpid()}] Scheduler Lock Acquired.")
    except (IOError, OSError):
        pass


def init_actual_scheduler():
    if not scheduler.get_job('main_sync_job'):
        scheduler.add_job(
            id='main_sync_job',
            func=scheduled_task,
            trigger="interval",
            minutes=5,
            next_run_time=datetime.now() + timedelta(seconds=60)
        )
        scheduler.start()


# הפעלה בתוך Greenlet כדי לא לחסום את עליית השרת
gevent.spawn(start_scheduler)

if __name__ == '__main__':
    socketio.run(app, debug=False, port=5000)