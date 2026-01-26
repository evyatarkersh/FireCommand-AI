from app.extensions import db
from datetime import datetime

class FireIncident(db.Model):
    __tablename__ = 'nasa_fires'

    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    brightness = db.Column(db.Float)
    frp = db.Column(db.Float)
    confidence = db.Column(db.String(20))
    source = db.Column(db.String(50))
    detected_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_processed = db.Column(db.Boolean, default=False)
    event_id = db.Column(db.Integer, db.ForeignKey('fire_events.id'), nullable=True)  # לאיזה אירוע זה שויך
    # מניעת כפילויות ברמת הדאטה-בייס
    __table_args__ = (
        db.UniqueConstraint('latitude', 'longitude', 'detected_at', 'source', name='unique_fire_detection_constraint'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'location': {'lat': self.latitude, 'lng': self.longitude},
            'brightness': self.brightness,
            'frp': self.frp,
            'timestamp': self.detected_at.isoformat(),
            'source': self.source
        }