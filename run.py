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
    """הפונקציה שתרוץ בכל סבב סנכרון"""
    with app.app_context():
        from app.api.routes import run_full_system_sync
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Starting sync cycle...")
        run_full_system_sync()


def init_actual_scheduler():
    """הגדרת ה-Job והתנעת ה-Scheduler"""
    if not scheduler.get_job('main_sync_job'):
        scheduler.add_job(
            id='main_sync_job',
            func=scheduled_task,
            trigger="interval",
            minutes=5,
            # הרצה ראשונה דקה אחרי העלייה
            next_run_time=datetime.now() + timedelta(seconds=60),
            misfire_grace_time=30
        )
        scheduler.start()


def start_scheduler_with_lock():
    """מנגנון מניעת כפילות מבוסס Port"""
    # השהיה של 5 שניות כדי לוודא שכל ה-Workers עלו
    gevent.sleep(5)

    try:
        # אנחנו מנסים "לתפוס" את פורט 5001.
        # רק תהליך אחד בכל השרת יכול להצליח בזה.
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', 5001))

        # אם הגענו לכאן - אנחנו ה-Worker הבלעדי!
        init_actual_scheduler()
        print(f"🚀 [PID {os.getpid()}] Port Lock Acquired (5001). Scheduler is the ONLY one running.")

        # שומרים על ה-socket פתוח לנצח כדי למנוע מאחרים לתפוס אותו
        while True:
            gevent.sleep(3600)

    except socket.error:
        # אם הפורט תפוס, התהליך הזה פשוט לא יפעיל scheduler
        print(f"ℹ️ [PID {os.getpid()}] Port 5001 busy. Another process is already handling the scheduler.")


# הרצת מנגנון הנעילה ברקע
gevent.spawn(start_scheduler_with_lock)

if __name__ == '__main__':
    socketio.run(app, debug=False, port=5000)