import socket
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

scheduler = GeventScheduler(job_defaults={'coalesce': True, 'max_instances': 1})

def scheduled_task():
    with app.app_context():
        from app.api.routes import run_full_system_sync
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Starting sync cycle...")
        run_full_system_sync()

def init_actual_scheduler():
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

def start_scheduler_with_lock():
    # השהיה של 10 שניות - קריטי כדי לוודא ש-Gunicorn סיים להקים את ה-Worker
    gevent.sleep(10)

    # ב-Render, אנחנו רוצים שה-Scheduler ירוץ רק בתוך ה-Worker.
    # ה-Master לא מגדיר את המשתנה הזה, רק ה-Worker.
    is_gunicorn_worker = os.environ.get('GUNICORN_WORKER_ID') is not None
    is_render = os.environ.get('RENDER') is not None

    if is_render and not is_gunicorn_worker:
        print(f"ℹ️ [PID {os.getpid()}] Master process ignored. Waiting for Worker to start scheduler.")
        return

    try:
        # ניסיון תפיסת פורט 5001
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', 5001))

        init_actual_scheduler()
        print(f"🚀 [PID {os.getpid()}] Port Lock Acquired. Scheduler running inside the ACTIVE Worker.")

        while True:
            gevent.sleep(3600)

    except socket.error:
        print(f"ℹ️ [PID {os.getpid()}] Port 5001 busy. Scheduler already handled.")

# הפעלה ברמה הגלובלית - כשה-Worker ייטען, הוא יריץ את זה
gevent.spawn(start_scheduler_with_lock)

if __name__ == '__main__':
    # לריצה לוקאלית בלבד (בלי Gunicorn)
    socketio.run(app, debug=False, port=5000)