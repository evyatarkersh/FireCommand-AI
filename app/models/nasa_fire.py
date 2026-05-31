from datetime import datetime

from app.extensions import db


class FireIncident(db.Model):
    """Database model representing fire incidents detected by NASA satellites. Stores geolocation, brightness, fire radiative power (FRP), confidence level, detection source, and assignment to fire events while preventing duplicate detections through unique constraints."""
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
    # Links this fire detection to a consolidated fire event
    event_id = db.Column(db.Integer, db.ForeignKey('fire_events.id'), nullable=True)
    # Prevent duplicates at the database level
    __table_args__ = (
        db.UniqueConstraint('latitude', 'longitude', 'detected_at', 'source', name='unique_fire_detection_constraint'),
    )

    def to_dict(self):
        """Converts the fire incident model to a dictionary format suitable for JSON serialization. Returns a dictionary containing the incident ID, geographic location as lat/lng pair, brightness, FRP, detection timestamp in ISO format, and source identifier."""
        return {
            'id': self.id,
            'location': {'lat': self.latitude, 'lng': self.longitude},
            'brightness': self.brightness,
            'frp': self.frp,
            'timestamp': self.detected_at.isoformat(),
            'source': self.source
        }
