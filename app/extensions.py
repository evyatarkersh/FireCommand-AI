from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')
print("🏠 SocketIO initialized in direct local mode")