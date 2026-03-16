from app.extensions import db


class Station(db.Model):
    __tablename__ = 'stations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(50))  # צפון, חוף, דן, מרכז, ירושלים, דרום
    station_type = db.Column(db.String(50))  # REGIONAL (מרכזית), SUB_STATION (משנית), AIRBASE (מנחת)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # קשר לכלים ששייכים לתחנה
    resources = db.relationship('Resource', backref='station', lazy=True)


class Resource(db.Model):
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    resource_type = db.Column(db.String(50),
                              nullable=False)  # SAAR (סער), ESHED (אשד), ROTEM (רותם), AIR_TRACTOR (מטוס)

    # סטטוס הכלי בזמן אמת
    status = db.Column(db.String(20), default='AVAILABLE')  # AVAILABLE, EN_ROUTE, ON_SCENE, MAINTENANCE

    # מיקום נוכחי (בברירת מחדל יהיה שווה למיקום התחנה)
    current_lat = db.Column(db.Float)
    current_lon = db.Column(db.Float)

    # לאיזה אירוע הוא מוקצה כרגע (Null אם הוא פנוי)
    assigned_event_id = db.Column(db.Integer, db.ForeignKey('fire_events.id'), nullable=True)