from app.extensions import db


class Station(db.Model):
    """
    Represents a fire station or airbase in the system. Each station has a geographic location, district assignment, and type classification (regional, sub-station, or airbase), and serves as a home base for firefighting resources.
    """
    __tablename__ = 'stations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # District classification: North, Coast, Dan, Center, Jerusalem, South
    district = db.Column(db.String(50))
    # Station type: REGIONAL (central), SUB_STATION (secondary), AIRBASE (airfield)
    station_type = db.Column(db.String(50))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # Relationship to resources assigned to this station
    resources = db.relationship('Resource', backref='station', lazy=True)


class Resource(db.Model):
    """
    Represents a firefighting resource (vehicle or aircraft) assigned to a station. Tracks the resource type, real-time operational status, current location, and assignment to active fire events.
    """
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    # Resource type: SAAR, ESHED, ROTEM, AIR_TRACTOR
    resource_type = db.Column(db.String(50),
                              nullable=False)

    # Real-time status of the resource: AVAILABLE, EN_ROUTE, ON_SCENE, MAINTENANCE
    status = db.Column(db.String(20), default='AVAILABLE')

    # Current location coordinates (defaults to station location if not specified)
    current_lat = db.Column(db.Float)
    current_lon = db.Column(db.Float)

    # Foreign key to the fire event this resource is currently assigned to (Null if available)
    assigned_event_id = db.Column(db.Integer, db.ForeignKey('fire_events.id'), nullable=True)


