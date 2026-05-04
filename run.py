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

if __name__ == '__main__':
    # לריצה לוקאלית בלבד
    socketio.run(app, debug=False, port=5000)