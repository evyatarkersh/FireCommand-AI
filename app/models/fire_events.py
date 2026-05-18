from app.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
import math


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
    
    # Topo Agent
    topo_elevation = db.Column(db.Float)
    topo_slope = db.Column(db.Float)
    topo_aspect = db.Column(db.Float)
    
    # IMS Agent
    ims_station_id = db.Column(db.Integer)
    ims_temp = db.Column(db.Float)

    ims_humidity = db.Column(db.Float)
    ims_wind_speed = db.Column(db.Float)
    ims_wind_dir = db.Column(db.Integer)
    ims_wind_gust = db.Column(db.Float)
    ims_rain = db.Column(db.Float)
    ims_radiation = db.Column(db.Float)
    
    # Fuel Agent
    fuel_type = db.Column(db.String(50))
    fuel_load = db.Column(db.Float)

    prediction_polygon = db.Column(JSONB)           # גבולות גזרה גיאוגרפיים (GeoJSON)
    pred_ros = db.Column(db.Float)                  # מהירות התפשטות במטרים/שעה
    pred_direction = db.Column(db.Float)            # אזימוט ההתפשטות (0-360)
    pred_flame_length = db.Column(db.Float)         # גובה להבה משוער במטרים
    pred_risk_level = db.Column(db.String(20))      # LOW, MODERATE, HIGH, EXTREME
    prediction_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    prediction_summary = db.Column(db.Text)
    
    # --- Commander Agent ---
    demand_perimeter_m = db.Column(db.Float) # דרישת קו ההגנה (במטרים) עבור הפוליגון החזוי הנוכחי

    tactical_summary = db.Column(db.String, nullable=True)
    
    # הקשר לנתונים הגולמיים
    raw_reads = db.relationship('FireIncident', backref='event', lazy=True)

    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """ חישוב מרחק אווירי (בקילומטרים) בין שתי קואורדינטות (Haversine) """
        R = 6371.0  # רדיוס כדור הארץ בק"מ
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
            dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    
    
    def to_dict(self):
        from app.models.resources import Station # ייבוא מקומי למניעת Circular Import
        all_stations = Station.query.all()
        
        # נמצא את המחוז של השריפה בשליפה (בדיוק כמו שהמפקד עושה)
        # הערה: עדיף לשמור את המחוז כעמודה ב-DB כדי לחסוך חישוב כל פעם
        district = "UNKNOWN"
        closest_station = None
        min_dist = float('inf')
        for station in all_stations:
            dist = self._calculate_distance(self.latitude, self.longitude, station.latitude, station.longitude)
            if dist < min_dist:
                min_dist = dist
                closest_station = station
        if closest_station:
            district = closest_station.district

        return {
            "event_id": self.id,
            "lat": self.latitude,
            "lon": self.longitude,
            "intensity": self.frp,
            "district": district, # <--- זה השדה הקריטי שחסר לריאקט!
            "created_at": self.created_at.isoformat(),
            "prediction_polygon": self.prediction_polygon,
            "prediction_summary": getattr(self, 'prediction_summary', "מחשב תחזית..."),
            "tactical_summary": getattr(self, 'tactical_summary', "מחשב סיכום טקטי...")
        }