from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os

db = SQLAlchemy()

# שליפת הכתובת שהגדרת ב-Render (משתנה הסביבה שהוספת)
redis_url = os.environ.get('REDIS_URL')

# הגדרת ה-SocketIO
# אם אנחנו ב-Render (ויש REDIS_URL), נוסיף את ה-message_queue
if redis_url:
    # הפרמטר message_queue הוא מה שמאפשר ל-Scheduler לשלוח נתונים ל-React
    # למרות שהם רצים בתהליכים נפרדים ב-Gunicorn
    socketio = SocketIO(
        cors_allowed_origins="*",
        async_mode='gevent',
        message_queue=redis_url
    )
    print(f"🌐 [PID {os.getpid()}] SocketIO initialized with Redis Message Queue")
else:
    # לוקאלית (בלי Redis) הכל ימשיך לעבוד כרגיל בתהליך אחד
    socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')
    print(f"🏠 [PID {os.getpid()}] SocketIO initialized in local mode (no Redis)")