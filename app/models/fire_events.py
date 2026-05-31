import math
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class FireEvent(db.Model):
    """
    Represents a fire event aggregated from multiple satellite detection points, storing location, intensity metrics, environmental enrichment data from various agents (weather, topography, IMS, fuel), and prediction/tactical analysis results for operational decision-making.
    """
    __tablename__ = 'fire_events'

    id = db.Column(db.Integer, primary_key=True)

    # --- Fire Center (calculated) ---
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # --- Sector Boundaries (Bounding Box) ---
    min_lat = db.Column(db.Float)
    max_lat = db.Column(db.Float)
    min_lon = db.Column(db.Float)
    max_lon = db.Column(db.Float)

    # --- Statistics ---
    num_points = db.Column(db.Integer, default=1)  # Number of satellite points that composed the event
    brightness = db.Column(db.Float)  # Maximum measured value
    frp = db.Column(db.Float)  # Maximum measured value
    confidence = db.Column(db.String(20))  # Of the most reliable/recent report
    source = db.Column(db.String(50))

    # --- Times and Status ---
    detected_at = db.Column(db.DateTime, nullable=False)  # Time of the first report
    last_update = db.Column(db.DateTime, default=datetime.utcnow)  # Time of the last report
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # --- Enrichment (Weather) ---
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

    prediction_polygon = db.Column(JSONB)  # Geographic sector boundaries (GeoJSON)
    pred_ros = db.Column(db.Float)  # Rate of spread in meters/hour
    pred_direction = db.Column(db.Float)  # Azimuth of spread (0-360)
    pred_flame_length = db.Column(db.Float)  # Estimated flame height in meters
    pred_risk_level = db.Column(db.String(20))  # LOW, MODERATE, HIGH, EXTREME
    prediction_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    prediction_summary = db.Column(db.Text)

    # --- Commander Agent ---
    demand_perimeter_m = db.Column(db.Float)  # Required defense line (in meters) for the current predicted polygon

    tactical_summary = db.Column(db.String, nullable=True)

    # Relation to raw data
    raw_reads = db.relationship('FireIncident', backref='event', lazy=True)

    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """
        Calculates the great-circle distance in kilometers between two geographic coordinates using the Haversine formula, taking latitude and longitude in decimal degrees and returning the air distance.
        """
        # Earth's radius in kilometers
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
            dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def to_dict(self):
        """
        Converts the fire event to a dictionary representation for API responses, including computed district based on proximity to the nearest fire station, prediction polygon, and tactical summaries.
        """
        # Local import to prevent circular dependency
        from app.models.resources import Station
        all_stations = Station.query.all()

        # Find the district of the fire by determining the closest station
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
            "district": district,
            "created_at": self.created_at.isoformat(),
            "prediction_polygon": self.prediction_polygon,
            "prediction_summary": getattr(self, 'prediction_summary', "מחשב תחזית..."),
            "tactical_summary": getattr(self, 'tactical_summary', "מחשב סיכום טקטי..."),
            "demand_perimeter_m": self.demand_perimeter_m or 0.0,
            "fuel_type": self.fuel_type or "Unknown Terrain",
            "risk": self.pred_risk_level or "MODERATE"
        }
