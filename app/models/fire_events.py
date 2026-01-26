from app.extensions import db
from datetime import datetime


# טבלה 1: האירוע העסקי (השריפה המאוחדת)
class FireEvent(db.Model):
    __tablename__ = 'fire_events'

    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    brightness = db.Column(db.Float)
    frp = db.Column(db.Float)
    confidence = db.Column(db.String(20))
    source = db.Column(db.String(50))
    detected_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # נתונים מועשרים מסוכנים אחרים (מזג אוויר וכו')
    owm_wind_speed = db.Column(db.Float)
    owm_wind_deg = db.Column(db.Integer)
    owm_temperature = db.Column(db.Float)
    owm_humidity = db.Column(db.Integer)

    # הקשר לנתונים הגולמיים
    raw_reads = db.relationship('FireIncident', backref='event', lazy=True)
