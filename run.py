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
    # השהיה כדי לוודא ש-Gunicorn סיים לעלות
    gevent.sleep(10)

    try:
        # ה-Socket הוא הדרך הכי טובה. לא משנה מי מנסה (Master או Worker),
        # רק אחד יצליח. הראשון שתופס - הוא זה שמריץ.
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', 5001))

        # אם הצלחנו לבצע bind, אנחנו ה-Instance היחיד שרשאי להריץ
        init_actual_scheduler()
        print(f"🚀 [PID {os.getpid()}] Port Lock Acquired. Scheduler starting...")

        # שמירה על הפורט תפוס
        while True:
            gevent.sleep(3600)

    except socket.error:
        # אם הפורט תפוס, התהליך הזה פשוט שותק
        print(f"ℹ️ [PID {os.getpid()}] Port 5001 busy. Scheduler already handled by another process.")

# הפעלה ברמה הגלובלית - כשה-Worker ייטען, הוא יריץ את זה
gevent.spawn(start_scheduler_with_lock)

if __name__ == '__main__':
    # לריצה לוקאלית בלבד (בלי Gunicorn)
    socketio.run(app, debug=False, port=5000)