from app.extensions import db
from datetime import datetime


class FireEvent(db.Model):
    __tablename__ = 'fire_events'

    id = db.Column(db.Integer, primary_key=True)

    # --- מרכז השריפה (מחושב) ---
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # --- גבולות הגזרה (Bounding Box) ---
    min_lat = db.Column(db.Float)
    max_lat = db.Column(db.Float)
    min_lon = db.Column(db.Float)
    max_lon = db.Column(db.Float)

    # --- סטטיסטיקות ---
    num_points = db.Column(db.Integer, default=1)  # כמה נקודות לוויין הרכיבו את האירוע
    brightness = db.Column(db.Float)  # המקסימלי שנמדד
    frp = db.Column(db.Float)  # המקסימלי שנמדד
    confidence = db.Column(db.String(20))  # של הדיווח הכי אמין/אחרון
    source = db.Column(db.String(50))

    # --- זמנים וסטטוס ---
    detected_at = db.Column(db.DateTime, nullable=False)  # הזמן של הדיווח הראשון
    last_update = db.Column(db.DateTime, default=datetime.utcnow)  # הזמן של הדיווח האחרון
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # --- העשרה (מזג אוויר) ---
    owm_wind_speed = db.Column(db.Float)
    owm_wind_deg = db.Column(db.Integer)
    owm_temperature = db.Column(db.Float)
    owm_humidity = db.Column(db.Integer)

    # --- העשרה (טופוגרפיה - הכנה) ---
    elevation = db.Column(db.Float)

    # הקשר לנתונים הגולמיים
    raw_reads = db.relationship('FireIncident', backref='event', lazy=True)