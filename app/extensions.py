from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()

# הגדרת ה-SocketIO עם אישור ל-CORS (כדי שהריאקט יוכל להתחבר אליו מפורט אחר)
socketio = SocketIO(cors_allowed_origins="*")