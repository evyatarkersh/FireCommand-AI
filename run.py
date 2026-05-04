import socket
import gevent.monkey
gevent.monkey.patch_all()

import os
from apscheduler.schedulers.gevent import GeventScheduler
from datetime import datetime, timedelta

from dotenv import load_dotenv # <--- הוספה חדשה
import os
from app.extensions import socketio
import redis

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
            # הרצה ראשונה 10 שניות אחרי הנעילה
            next_run_time=datetime.now() + timedelta(seconds=10),
            misfire_grace_time=30
        )
        scheduler.start()


def start_scheduler_with_redis_lock():
    """מנגנון מניעת כפילות מבוסס Redis"""
    # השהיה כדי לוודא ש-Gunicorn סיים לעלות לגמרי
    gevent.sleep(10)

    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        print("⚠️ No REDIS_URL found. Running in local mode without lock.")
        init_actual_scheduler()
        return

    try:
        # חיבור ל-Redis
        r = redis.from_url(redis_url)

        # ניסיון ליצור מפתח נעילה. nx=True מבטיח שרק הראשון מצליח.
        # ex=300 קובע שהנעילה תפוג אוטומטית אחרי 5 דקות אם השרת קרס.
        lock_acquired = r.set("scheduler_lock", "active", nx=True, ex=300)

        if lock_acquired:
            init_actual_scheduler()
            print(f"🚀 [PID {os.getpid()}] Redis Lock Acquired. Scheduler is running.")

            # לולאת רענון: כל דקה אנחנו מאריכים את הנעילה לעוד 5 דקות
            # זה מבטיח שהנעילה לא תפוג כל עוד התהליך הזה בחיים
            while True:
                gevent.sleep(60)
                r.expire("scheduler_lock", 300)
        else:
            print(f"ℹ️ [PID {os.getpid()}] Scheduler already running on another instance (Redis lock busy).")

    except Exception as e:
        print(f"❌ Redis Lock Error: {e}")


# הרצה ברקע דרך gevent
gevent.spawn(start_scheduler_with_redis_lock)

if __name__ == '__main__':
    # לריצה לוקאלית בלבד
    socketio.run(app, debug=False, port=5000)